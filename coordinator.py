"""Data coordinator for the Spider Farmer GGS Controller."""
from __future__ import annotations

import asyncio
import json
import logging
import os
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

# How long to wait for a BLE connection before giving up. Must stay well under
# Home Assistant's config entry setup timeout: if setup is still blocked when
# that fires, the CancelledError escapes `except Exception` (it is a
# BaseException) and the entry lands in setup_error, which never retries.
CONNECT_TIMEOUT = 30

# Commands sent on every poll, overridable at runtime without a restart.
POLL_COMMANDS_FILE = os.path.join(os.path.dirname(__file__), "poll_commands.json")
DEFAULT_POLL_COMMANDS = [{"method": "getDevSta"}]


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
    alarm_time: Optional[datetime] = None
    alarm_type: Optional[int] = None
    alarm_dev_type: Optional[int] = None

    # ── Last operation log ──────────────────────────────────────────────────────
    oplog_time: Optional[datetime] = None
    oplog_dev_type: Optional[int] = None
    oplog_mode_type: Optional[int] = None

    # ── Device mode types ────────────────────────────────────────────────────
    light_mode: Optional[int] = None
    light2_mode: Optional[int] = None
    fan_mode: Optional[int] = None
    blower_mode: Optional[int] = None
    humidifier_mode: Optional[int] = None

    # ── Fan/Blower extended settings ─────────────────────────────────────────
    fan_max_speed: Optional[int] = None
    fan_min_speed: Optional[int] = None
    fan_shake_level: Optional[int] = None
    fan_natural: Optional[bool] = None
    blower_max_speed: Optional[int] = None
    blower_min_speed: Optional[int] = None

    # ── Cached config blocks (for building setConfigField payloads) ──────────
    _light_config: Optional[dict] = field(default=None, repr=False)
    _light2_config: Optional[dict] = field(default=None, repr=False)
    _fan_config: Optional[dict] = field(default=None, repr=False)
    _blower_config: Optional[dict] = field(default=None, repr=False)
    _humidifier_config: Optional[dict] = field(default=None, repr=False)

    # ── Light schedule/PPFD settings ─────────────────────────────────────────
    light_schedule_brightness: Optional[int] = None
    light_schedule_start: Optional[int] = None  # seconds since midnight
    light_schedule_end: Optional[int] = None
    light_fade_time: Optional[int] = None  # seconds
    light_ppfd_target: Optional[int] = None
    light_ppfd_start: Optional[int] = None
    light_ppfd_end: Optional[int] = None
    light_ppfd_fade: Optional[int] = None
    light_dimming_min: Optional[int] = None
    light_dimming_max: Optional[int] = None
    light_dim_threshold: Optional[float] = None
    light_off_threshold: Optional[float] = None

    light2_schedule_brightness: Optional[int] = None
    light2_schedule_start: Optional[int] = None
    light2_schedule_end: Optional[int] = None
    light2_fade_time: Optional[int] = None
    light2_ppfd_target: Optional[int] = None
    light2_ppfd_start: Optional[int] = None
    light2_ppfd_end: Optional[int] = None
    light2_ppfd_fade: Optional[int] = None
    light2_dimming_min: Optional[int] = None
    light2_dimming_max: Optional[int] = None
    light2_dim_threshold: Optional[float] = None
    light2_off_threshold: Optional[float] = None

    # ── Fan schedule/cycle settings ──────────────────────────────────────────
    fan_schedule_start: Optional[int] = None
    fan_schedule_end: Optional[int] = None
    fan_cycle_start: Optional[int] = None
    fan_cycle_run: Optional[int] = None  # seconds
    fan_cycle_off: Optional[int] = None  # seconds
    fan_cycle_times: Optional[int] = None

    # ── Blower schedule/cycle settings ───────────────────────────────────────
    blower_schedule_start: Optional[int] = None
    blower_schedule_end: Optional[int] = None
    blower_cycle_start: Optional[int] = None
    blower_cycle_run: Optional[int] = None
    blower_cycle_off: Optional[int] = None
    blower_cycle_times: Optional[int] = None

    # ── Humidifier schedule/cycle settings ───────────────────────────────────
    humidifier_schedule_start: Optional[int] = None
    humidifier_schedule_end: Optional[int] = None
    humidifier_cycle_start: Optional[int] = None
    humidifier_cycle_run: Optional[int] = None
    humidifier_cycle_off: Optional[int] = None
    humidifier_cycle_times: Optional[int] = None


def _get_level(device_dict: dict) -> Optional[int]:
    """Get 'level' from a device dict, handling BLE-corrupted key names."""
    if "level" in device_dict:
        return int(device_dict["level"])
    for k, v in device_dict.items():
        if "evel" in k and isinstance(v, (int, float)):
            return int(v)
    return None


def _epoch_to_dt(epoch: int) -> datetime:
    """Convert a Unix epoch to a timezone-aware datetime object."""
    return datetime.fromtimestamp(epoch, tz=timezone.utc)


# Keys that only ever appear in a full config block (from getConfigField), never
# in the cut-down runtime view getDevSta returns, which is just on/level/modeType.
_CONFIG_ONLY_KEYS = frozenset({
    "mLevel", "mOnOff", "timePeriod", "cycleTime",
    "maxSpeed", "minSpeed", "shakeLevel", "ppfdPeriod",
})


def _is_config_block(block: dict) -> bool:
    """True if this looks like a full config block rather than runtime state.

    setConfigField writes back whatever is cached, so caching a runtime block
    would send it as the new config and wipe the module's schedule and cycle
    settings on the controller. Seen happening 2026-08-16.
    """
    return bool(_CONFIG_ONLY_KEYS.intersection(block))


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
        self._capture: Optional[list[str]] = None
        self.data = GGSData()

    # ── Coordinator lifecycle ─────────────────────────────────────────────────

    async def _async_update_data(self) -> GGSData:
        try:
            await self._ensure_connected()
            for command in await self._async_poll_commands():
                await self._send_raw(command)
                await asyncio.sleep(2)
            return self.data
        except BleakError as exc:
            self._client = None
            raise UpdateFailed(f"BLE error: {exc}") from exc
        except Exception as exc:
            self._client = None
            raise UpdateFailed(f"Unexpected error: {exc}") from exc

    async def _async_poll_commands(self) -> list[dict]:
        """Commands sent on every poll.

        Read from poll_commands.json next to this file so the list can be changed
        without a restart — an edit takes effect on the next poll. Falls back to
        getDevSta alone if the file is missing or unreadable.
        """
        def _read() -> list[dict]:
            try:
                with open(POLL_COMMANDS_FILE, encoding="utf-8") as handle:
                    commands = json.load(handle)
            except FileNotFoundError:
                return list(DEFAULT_POLL_COMMANDS)
            except (OSError, json.JSONDecodeError) as exc:
                _LOGGER.warning(
                    "Spider Farmer GGS: %s unreadable (%s) — using default poll commands",
                    POLL_COMMANDS_FILE, exc,
                )
                return list(DEFAULT_POLL_COMMANDS)
            if not isinstance(commands, list) or not all(
                isinstance(c, dict) for c in commands
            ):
                _LOGGER.warning(
                    "Spider Farmer GGS: %s must be a list of command objects — "
                    "using default poll commands", POLL_COMMANDS_FILE,
                )
                return list(DEFAULT_POLL_COMMANDS)
            return commands or list(DEFAULT_POLL_COMMANDS)

        return await self.hass.async_add_executor_job(_read)

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

        # establish_connection retries internally and can block for minutes when
        # the controller advertises but will not accept a connection — e.g. the
        # Spider Farmer app holds its single BLE slot. Cap it so that turns into
        # a normal retry instead of a setup_error the entry never recovers from.
        try:
            async with asyncio.timeout(CONNECT_TIMEOUT):
                self._client = await establish_connection(
                    BleakClientWithServiceCache,
                    ble_device,
                    self.mac_address,
                    disconnected_callback=self._handle_disconnect,
                )
        except TimeoutError as exc:
            self._client = None
            raise UpdateFailed(
                f"Timed out after {CONNECT_TIMEOUT}s connecting to {self.mac_address}. "
                "The controller may be connected to the Spider Farmer app, which "
                "takes its only BLE connection."
            ) from exc

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

        if self._capture is not None:
            self._capture.append(json_str)

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
            self.data.alarm_time = _epoch_to_dt(alarm["epoch"])
        if "alarmType" in alarm:
            self.data.alarm_type = alarm["alarmType"]
        if "devType" in alarm:
            self.data.alarm_dev_type = alarm["devType"]

    def _parse_oplog(self, data: dict) -> None:
        oplog = data.get("oplogLast", {})
        if not oplog:
            return
        if "epoch" in oplog:
            self.data.oplog_time = _epoch_to_dt(oplog["epoch"])
        if "devType" in oplog:
            self.data.oplog_dev_type = oplog["devType"]
        if "modeType" in oplog:
            self.data.oplog_mode_type = oplog["modeType"]

    # ── Device parsing ────────────────────────────────────────────────────────

    def _parse_light_settings(self, data: dict, module: str, prefix: str) -> None:
        """Parse schedule/PPFD settings from a light config block."""
        light = data.get(module, {})
        if not light:
            return
        d = self.data

        # timePeriod (Schedule mode settings)
        tp = light.get("timePeriod", [])
        if tp and isinstance(tp, list) and len(tp) > 0:
            period = tp[0]
            setattr(d, f"{prefix}_schedule_brightness", period.get("brightness"))
            setattr(d, f"{prefix}_schedule_start", period.get("startTime"))
            setattr(d, f"{prefix}_schedule_end", period.get("endTime"))
            setattr(d, f"{prefix}_fade_time", period.get("fadeTime"))

        # ppfdPeriod (PPFD mode settings)
        pp = light.get("ppfdPeriod", [])
        if pp and isinstance(pp, list) and len(pp) > 0:
            period = pp[0]
            setattr(d, f"{prefix}_ppfd_target", period.get("brightness"))
            setattr(d, f"{prefix}_ppfd_start", period.get("startTime"))
            setattr(d, f"{prefix}_ppfd_end", period.get("endTime"))
            setattr(d, f"{prefix}_ppfd_fade", period.get("fadeTime"))

        # Dimming range
        setattr(d, f"{prefix}_dimming_min", light.get("ppfdMinBrightness"))
        setattr(d, f"{prefix}_dimming_max", light.get("ppfdMaxBrightness"))

        # Temperature protection
        setattr(d, f"{prefix}_dim_threshold", light.get("darkTemp"))
        setattr(d, f"{prefix}_off_threshold", light.get("offTemp"))

    def _parse_fan_settings(self, data: dict, module: str, prefix: str) -> None:
        """Parse schedule/cycle settings from a fan/blower config block."""
        device = data.get(module, {})
        if not device:
            return
        d = self.data

        # timePeriod (Schedule mode)
        tp = device.get("timePeriod", [])
        if tp and isinstance(tp, list) and len(tp) > 0:
            period = tp[0]
            setattr(d, f"{prefix}_schedule_start", period.get("startTime"))
            setattr(d, f"{prefix}_schedule_end", period.get("endTime"))

        # cycleTime (Cycle mode)
        ct = device.get("cycleTime", {})
        if ct:
            setattr(d, f"{prefix}_cycle_start", ct.get("startTime"))
            setattr(d, f"{prefix}_cycle_run", ct.get("openDur"))
            setattr(d, f"{prefix}_cycle_off", ct.get("closeDur"))
            setattr(d, f"{prefix}_cycle_times", ct.get("times"))

    def _parse_devices(self, data: dict) -> None:
        # Fan
        fan = data.get("fan", {})
        if fan and _is_config_block(fan):
            self.data._fan_config = dict(fan)
        if "on" in fan:
            self.data.fan_on = bool(fan["on"])
        level = _get_level(fan)
        if level is not None:
            self.data.fan_level = level
            if "on" not in fan:
                self.data.fan_on = level > 0
        if "modeType" in fan:
            self.data.fan_mode = fan["modeType"]
        if "maxSpeed" in fan:
            self.data.fan_max_speed = fan["maxSpeed"]
        if "minSpeed" in fan:
            self.data.fan_min_speed = fan["minSpeed"]
        if "shakeLevel" in fan:
            self.data.fan_shake_level = fan["shakeLevel"]
        if "natural" in fan:
            self.data.fan_natural = bool(fan["natural"])

        # Grow light 1
        light = data.get("light", {})
        if light and _is_config_block(light):
            self.data._light_config = dict(light)
        if "on" in light:
            self.data.light_on = bool(light["on"])
        level = _get_level(light)
        if level is not None:
            self.data.light_level = level
            if "on" not in light:
                self.data.light_on = level > 0
        if "modeType" in light:
            self.data.light_mode = light["modeType"]

        # Grow light 2
        light2 = data.get("light2", {})
        if light2 and _is_config_block(light2):
            self.data._light2_config = dict(light2)
        level = _get_level(light2)
        if level is not None:
            self.data.light2_level = level
            if "on" in light2:
                self.data.light2_on = bool(light2["on"])
            else:
                self.data.light2_on = level > 0
        if "modeType" in light2:
            self.data.light2_mode = light2["modeType"]

        # Blower
        blower = data.get("blower", {})
        if blower and _is_config_block(blower):
            self.data._blower_config = dict(blower)
        if "on" in blower:
            self.data.blower_on = bool(blower["on"])
        level = _get_level(blower)
        if level is not None:
            self.data.blower_level = level
            if "on" not in blower:
                self.data.blower_on = level > 0
        if "modeType" in blower:
            self.data.blower_mode = blower["modeType"]
        if "maxSpeed" in blower:
            self.data.blower_max_speed = blower["maxSpeed"]
        if "minSpeed" in blower:
            self.data.blower_min_speed = blower["minSpeed"]

        # Humidifier
        humidifier = data.get("humidifier", {})
        if humidifier and _is_config_block(humidifier):
            self.data._humidifier_config = dict(humidifier)
        if "on" in humidifier:
            self.data.humidifier_on = bool(humidifier["on"])
        level = _get_level(humidifier)
        if level is not None:
            self.data.humidifier_level = level
            if "on" not in humidifier:
                self.data.humidifier_on = level > 0
        if "modeType" in humidifier:
            self.data.humidifier_mode = humidifier["modeType"]

        # Heater
        heater = data.get("heater", {})
        if "on" in heater:
            self.data.heater_on = bool(heater["on"])
        level = _get_level(heater)
        if level is not None:
            self.data.heater_level = level
            if "on" not in heater:
                self.data.heater_on = level > 0

        self._parse_light_settings(data, "light", "light")
        self._parse_light_settings(data, "light2", "light2")
        self._parse_fan_settings(data, "fan", "fan")
        self._parse_fan_settings(data, "blower", "blower")
        self._parse_fan_settings(data, "humidifier", "humidifier")

    # ── Device control commands ───────────────────────────────────────────────

    async def _send_raw(self, command: dict) -> None:
        await self._ensure_connected()
        payload = json.dumps(command, separators=(",", ":")).encode("utf-8")
        await self._client.write_gatt_char(UUID_WRITE, payload, response=True)

    async def async_probe(self, command: dict, wait: float = 3.0) -> list[dict]:
        """Send an arbitrary command and return whatever the controller replies.

        Used to discover protocol commands the integration does not implement yet.
        The controller also pushes unsolicited status every few seconds, so the
        result can include messages unrelated to this command — check the
        `method` field of each.
        """
        self._capture = []
        try:
            await self._send_raw(command)
            await asyncio.sleep(wait)
            captured = list(self._capture)
        finally:
            self._capture = None

        replies = []
        for raw in captured:
            try:
                replies.append(json.loads(raw))
            except json.JSONDecodeError:
                replies.append({"unparsed": raw[:500]})
        return replies

    async def async_send_config_field(self, module: str, config: dict) -> None:
        """Send a setConfigField command to change device mode/settings."""
        payload = {
            "method": "setConfigField",
            "params": {
                "keyPath": ["device", module],
                module: config,
            },
        }
        _LOGGER.debug("GGS setConfigField %s: %s", module, json.dumps(config))
        await self._send_raw(payload)
        # Wait for controller to process, then poll for updated state
        await asyncio.sleep(2)
        await self._send_raw({"method": "getDevSta"})
        await asyncio.sleep(2)
        self.async_update_listeners()

    def _build_config_block(self, module: str, overrides: dict) -> dict:
        """Build a full config block for a module by merging overrides into cached state.

        The controller needs a reasonably complete config block — partial updates
        work for some fields but not others. We merge our changes into whatever
        the controller last reported.
        """
        cache_map = {
            "light": self.data._light_config,
            "light2": self.data._light2_config,
            "fan": self.data._fan_config,
            "blower": self.data._blower_config,
            "humidifier": self.data._humidifier_config,
        }
        cached = cache_map.get(module)
        if cached:
            block = dict(cached)
            block.update(overrides)
        else:
            block = dict(overrides)
        return block

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
