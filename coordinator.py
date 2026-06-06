"""Data coordinator for the Spider Farmer GGS Controller."""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from bleak import BleakClient, BleakError
from bleak_retry_connector import establish_connection, BleakClientWithServiceCache

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UUID_NOTIFY, UUID_WRITE

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)


@dataclass
class SoilProbeData:
    """Data from a single soil probe."""
    probe_id: Optional[str] = None
    temperature: Optional[float] = None
    water_content: Optional[float] = None
    ec: Optional[float] = None


@dataclass
class GGSData:
    """Holds all data fields reported by the GGS controller."""
    # ── Environment sensors ────────────────────────────────────────────────────
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    vpd: Optional[float] = None
    co2: Optional[float] = None
    ppfd: Optional[float] = None
    is_day_env_target: Optional[bool] = None

    # ── Soil probes (individual) ───────────────────────────────────────────────
    soil_probe_1: SoilProbeData = field(default_factory=SoilProbeData)
    soil_probe_2: SoilProbeData = field(default_factory=SoilProbeData)
    soil_probe_3: SoilProbeData = field(default_factory=SoilProbeData)

    # ── Soil averages ──────────────────────────────────────────────────────────
    soil_avg_temp: Optional[float] = None
    soil_avg_wc: Optional[float] = None
    soil_avg_ec: Optional[float] = None

    # ── Grow plan ──────────────────────────────────────────────────────────────
    plan_active: Optional[bool] = None
    plan_days_remaining: Optional[int] = None
    plan_days_elapsed: Optional[int] = None
    plan_total_days: Optional[int] = None
    plan_progress: Optional[int] = None

    # ── Fan ─────────────────────────────────────────────────────────────────────
    fan_on: Optional[bool] = None
    fan_level: Optional[int] = None

    # ── Grow light 1 ───────────────────────────────────────────────────────────
    light_on: Optional[bool] = None
    light_level: Optional[int] = None

    # ── Grow light 2 ───────────────────────────────────────────────────────────
    light2_on: Optional[bool] = None
    light2_level: Optional[int] = None

    # ── Blower ──────────────────────────────────────────────────────────────────
    blower_on: Optional[bool] = None
    blower_level: Optional[int] = None

    # ── Humidifier ──────────────────────────────────────────────────────────────
    humidifier_on: Optional[bool] = None
    humidifier_level: Optional[int] = None

    # ── Heater ──────────────────────────────────────────────────────────────────
    heater_on: Optional[bool] = None
    heater_level: Optional[int] = None

    # ── Last alarm ──────────────────────────────────────────────────────────────
    alarm_time: Optional[str] = None
    alarm_type: Optional[int] = None
    alarm_dev_type: Optional[int] = None

    # ── Last operation log ──────────────────────────────────────────────────────
    oplog_time: Optional[str] = None
    oplog_dev_type: Optional[int] = None
    oplog_mode_type: Optional[int] = None


def _get_level(device_dict: dict) -> Optional[int]:
    """Get 'level' from a device dict, handling BLE-corrupted key names."""
    if "level" in device_dict:
        return int(device_dict["level"])
    for k, v in device_dict.items():
        if "evel" in k and isinstance(v, (int, float)):
            return int(v)
    return None


def _epoch_to_iso(epoch: int) -> str:
    """Convert a Unix epoch to an ISO 8601 UTC string."""
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


class SpiderFarmerGGSCoordinator(DataUpdateCoordinator[GGSData]):
    """Manages the BLE connection and data for the Spider Farmer GGS Controller."""

    def __init__(self, hass: HomeAssistant, mac_address: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.mac_address = mac_address.upper()
        self._client: Optional[BleakClient] = None
        self._raw_packets: list[bytes] = []
        self._logged_full_payload = False
        self.data = GGSData()

    # ── Coordinator lifecycle ─────────────────────────────────────────────────

    async def _async_update_data(self) -> GGSData:
        try:
            await self._ensure_connected()
            await self._send_raw({"method": "getDevSta"})
            await asyncio.sleep(2)
            return self.data
        except BleakError as exc:
            self._client = None
            raise UpdateFailed(f"BLE error: {exc}") from exc
        except Exception as exc:
            self._client = None
            raise UpdateFailed(f"Unexpected error: {exc}") from exc

    # ── Connection management ─────────────────────────────────────────────────

    async def _ensure_connected(self) -> None:
        if self._client and self._client.is_connected:
            return

        ble_device = async_ble_device_from_address(
            self.hass, self.mac_address, connectable=True
        )
        if ble_device is None:
            raise UpdateFailed(
                f"Device {self.mac_address} not visible to HA bluetooth scanner. "
                "Ensure the controller is powered on and within range."
            )

        self._client = await establish_connection(
            BleakClientWithServiceCache,
            ble_device,
            self.mac_address,
            disconnected_callback=self._handle_disconnect,
        )
        await self._client.start_notify(UUID_NOTIFY, self._notification_handler)
        _LOGGER.debug("Spider Farmer GGS: connected and notifications subscribed")

    def _handle_disconnect(self, _client: BleakClient) -> None:
        if self._client is not None:
            _LOGGER.warning(
                "Spider Farmer GGS: disconnected — will reconnect on next poll"
            )
            self._client = None

    async def async_disconnect(self) -> None:
        if self._client and self._client.is_connected:
            await self._client.disconnect()
        self._client = None

    # ── BLE notification handling ─────────────────────────────────────────────

    def _notification_handler(self, _sender, data: bytearray) -> None:
        _LOGGER.debug(
            "Spider Farmer GGS: raw %d bytes hex[0:20]=%s",
            len(data), data[:20].hex(" "),
        )

        marker = b'{"method":'
        pos = data.find(marker)

        if 0 <= pos < 30:
            self._raw_packets = [data[pos:]]
        elif self._raw_packets:
            self._raw_packets.append(bytes(data))
        else:
            return

        self._try_assemble()

    def _try_assemble(self) -> None:
        if not self._raw_packets:
            return

        base = "".join(chr(b) for b in self._raw_packets[0] if 32 <= b <= 126)

        if len(self._raw_packets) < 2:
            depth = 0
            for ch in base:
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        self._raw_packets.clear()
                        self._parse_payload(base)
                        return
            if len(base) > 4000:
                self._raw_packets.clear()
            return

        for strip_len in range(0, 35):
            parts = [base]
            for pkt in self._raw_packets[1:]:
                trimmed = pkt[strip_len:] if strip_len < len(pkt) else b""
                parts.append(
                    "".join(chr(b) for b in trimmed if 32 <= b <= 126)
                )
            combined = "".join(parts)

            depth = 0
            end = -1
            for i, ch in enumerate(combined):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break

            if end < 0:
                continue

            candidate = combined[:end]
            try:
                json.loads(candidate)
            except json.JSONDecodeError:
                continue

            _LOGGER.debug(
                "Spider Farmer GGS: assembled %d bytes, continuation strip=%d",
                len(candidate), strip_len,
            )
            self._raw_packets.clear()
            self._parse_payload(candidate)
            return

        if sum(len(p) for p in self._raw_packets) > 4000:
            _LOGGER.debug("Spider Farmer GGS: clearing oversized raw buffer")
            self._raw_packets.clear()

    def _parse_payload(self, json_str: str) -> None:
        try:
            msg = json.loads(json_str)
        except json.JSONDecodeError as exc:
            _LOGGER.debug("Spider Farmer GGS: JSON parse error %s", exc)
            return

        if not self._logged_full_payload:
            _LOGGER.warning(
                "Spider Farmer GGS — FULL DEVICE PAYLOAD (logged once):\n%s",
                json.dumps(msg, indent=2),
            )
            self._logged_full_payload = True

        raw = msg.get("data", {})
        if not raw:
            return

        self._parse_sensors(raw)
        self._parse_soil_probes(raw)
        self._parse_plan(raw)
        self._parse_devices(raw)
        self._parse_alarm(raw)
        self._parse_oplog(raw)

    # ── Sensor parsing ────────────────────────────────────────────────────────

    def _parse_sensors(self, data: dict) -> None:
        sensor = data.get("sensor", {})

        # Air temperature
        if "temp" in sensor:
            t = sensor["temp"]
            if isinstance(t, (int, float)) and -20 <= t <= 60:
                self.data.temperature = t

        # Humidity — device uses "humi" or "humiv"
        for key in ("humi", "humiv"):
            if key in sensor:
                self.data.humidity = sensor[key]
                break

        if "vpd" in sensor:
            self.data.vpd = sensor["vpd"]

        for key in ("co2", "CO2"):
            if key in sensor:
                self.data.co2 = sensor[key]
                break

        for key in ("ppfd", "PPFD", "par", "PAR"):
            if key in sensor:
                self.data.ppfd = sensor[key]
                break

        # Soil averages (from the sensor block)
        if "tempSoil" in sensor:
            self.data.soil_avg_temp = sensor["tempSoil"]
        if "humiSoil" in sensor:
            self.data.soil_avg_wc = sensor["humiSoil"]
        if "ECSoil" in sensor:
            self.data.soil_avg_ec = sensor["ECSoil"]

        # Environment target
        if "isDayEnvTarget" in sensor:
            self.data.is_day_env_target = bool(sensor["isDayEnvTarget"])

    def _parse_soil_probes(self, data: dict) -> None:
        sensors_list = data.get("sensors", [])
        probe_slots = [self.data.soil_probe_1, self.data.soil_probe_2, self.data.soil_probe_3]
        probe_idx = 0

        for entry in sensors_list:
            if entry.get("id") == "avg":
                continue
            if probe_idx >= 3:
                break

            slot = probe_slots[probe_idx]
            slot.probe_id = entry.get("id")
            if "tempSoil" in entry:
                slot.temperature = entry["tempSoil"]
            if "humiSoil" in entry:
                slot.water_content = entry["humiSoil"]
            if "ECSoil" in entry:
                slot.ec = entry["ECSoil"]
            probe_idx += 1

    def _parse_plan(self, data: dict) -> None:
        plan = data.get("plan", {})
        if not plan:
            return

        if "isPlanRun" in plan:
            self.data.plan_active = bool(plan["isPlanRun"])
        if "planRemainDays" in plan:
            self.data.plan_days_remaining = plan["planRemainDays"]
        if "planedDays" in plan:
            self.data.plan_days_elapsed = plan["planedDays"]
        if "planedTotalDays" in plan:
            self.data.plan_total_days = plan["planedTotalDays"]
        if "planProgress" in plan:
            self.data.plan_progress = plan["planProgress"]

    def _parse_alarm(self, data: dict) -> None:
        alarm = data.get("alarmLast", {})
        if not alarm:
            return
        if "epoch" in alarm:
            self.data.alarm_time = _epoch_to_iso(alarm["epoch"])
        if "alarmType" in alarm:
            self.data.alarm_type = alarm["alarmType"]
        if "devType" in alarm:
            self.data.alarm_dev_type = alarm["devType"]

    def _parse_oplog(self, data: dict) -> None:
        oplog = data.get("oplogLast", {})
        if not oplog:
            return
        if "epoch" in oplog:
            self.data.oplog_time = _epoch_to_iso(oplog["epoch"])
        if "devType" in oplog:
            self.data.oplog_dev_type = oplog["devType"]
        if "modeType" in oplog:
            self.data.oplog_mode_type = oplog["modeType"]

    # ── Device parsing ────────────────────────────────────────────────────────

    def _parse_devices(self, data: dict) -> None:
        # Fan
        fan = data.get("fan", {})
        if "on" in fan:
            self.data.fan_on = bool(fan["on"])
        level = _get_level(fan)
        if level is not None:
            self.data.fan_level = level
            if "on" not in fan:
                self.data.fan_on = level > 0

        # Grow light 1
        light = data.get("light", {})
        if "on" in light:
            self.data.light_on = bool(light["on"])
        level = _get_level(light)
        if level is not None:
            self.data.light_level = level
            if "on" not in light:
                self.data.light_on = level > 0

        # Grow light 2
        light2 = data.get("light2", {})
        level = _get_level(light2)
        if level is not None:
            self.data.light2_level = level
            if "on" in light2:
                self.data.light2_on = bool(light2["on"])
            else:
                self.data.light2_on = level > 0

        # Blower
        blower = data.get("blower", {})
        if "on" in blower:
            self.data.blower_on = bool(blower["on"])
        level = _get_level(blower)
        if level is not None:
            self.data.blower_level = level
            if "on" not in blower:
                self.data.blower_on = level > 0

        # Humidifier
        humidifier = data.get("humidifier", {})
        if "on" in humidifier:
            self.data.humidifier_on = bool(humidifier["on"])
        level = _get_level(humidifier)
        if level is not None:
            self.data.humidifier_level = level
            if "on" not in humidifier:
                self.data.humidifier_on = level > 0

        # Heater
        heater = data.get("heater", {})
        if "on" in heater:
            self.data.heater_on = bool(heater["on"])
        level = _get_level(heater)
        if level is not None:
            self.data.heater_level = level
            if "on" not in heater:
                self.data.heater_on = level > 0

    # ── Device control commands ───────────────────────────────────────────────

    async def _send_raw(self, command: dict) -> None:
        await self._ensure_connected()
        payload = json.dumps(command, separators=(",", ":")).encode("utf-8")
        await self._client.write_gatt_char(UUID_WRITE, payload, response=True)

    async def async_set_fan(self, on: bool, level: Optional[int] = None) -> None:
        cmd: dict = {"on": 1 if on else 0}
        if level is not None:
            cmd["level"] = level
        await self._send_raw({"method": "setFan", "data": cmd})
        self.data.fan_on = on
        if level is not None:
            self.data.fan_level = level
        self.async_update_listeners()

    async def async_set_light(self, on: bool, level: Optional[int] = None) -> None:
        cmd: dict = {"modeType": 0, "on": 1 if on else 0}
        if level is not None:
            cmd["level"] = level
        await self._send_raw({"method": "setLight", "data": cmd})
        self.data.light_on = on
        if level is not None:
            self.data.light_level = level
        self.async_update_listeners()

    async def async_set_light2(self, on: bool, level: Optional[int] = None) -> None:
        cmd: dict = {"modeType": 0, "on": 1 if on else 0}
        if level is not None:
            cmd["level"] = level
        await self._send_raw({"method": "setLight2", "data": cmd})
        self.data.light2_on = on
        if level is not None:
            self.data.light2_level = level
        self.async_update_listeners()

    async def async_set_blower(self, on: bool, level: Optional[int] = None) -> None:
        cmd: dict = {"modeType": 0, "on": 1 if on else 0}
        if level is not None:
            cmd["level"] = level
        await self._send_raw({"method": "setBlower", "data": cmd})
        self.data.blower_on = on
        if level is not None:
            self.data.blower_level = level
        self.async_update_listeners()

    async def async_set_humidifier(self, on: bool, level: Optional[int] = None) -> None:
        cmd: dict = {"on": 1 if on else 0}
        if level is not None:
            cmd["level"] = level
        await self._send_raw({"method": "setHumidifier", "data": cmd})
        self.data.humidifier_on = on
        if level is not None:
            self.data.humidifier_level = level
        self.async_update_listeners()

    async def async_set_heater(self, on: bool, level: Optional[int] = None) -> None:
        cmd: dict = {"on": 1 if on else 0}
        if level is not None:
            cmd["level"] = level
        await self._send_raw({"method": "setHeater", "data": cmd})
        self.data.heater_on = on
        if level is not None:
            self.data.heater_level = level
        self.async_update_listeners()
