"""Service handlers for Spider Farmer GGS Controller."""
from __future__ import annotations

import logging
from datetime import time as dt_time

from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN, FAN_MODES, HUMIDIFIER_MODES, LIGHT_MODES
from .coordinator import SpiderFarmerGGSCoordinator

_LOGGER = logging.getLogger(__name__)


def _time_to_seconds(t) -> int:
    """Convert a time string 'HH:MM' or time object to seconds since midnight."""
    if isinstance(t, dt_time):
        return t.hour * 3600 + t.minute * 60
    if isinstance(t, str) and ":" in t:
        parts = t.split(":")
        return int(parts[0]) * 3600 + int(parts[1]) * 60
    return 0


def _get_coordinator(hass: HomeAssistant) -> SpiderFarmerGGSCoordinator:
    """Get the first (and typically only) coordinator instance."""
    data = hass.data.get(DOMAIN, {})
    for coordinator in data.values():
        return coordinator
    raise ValueError("No Spider Farmer GGS integration found")


async def async_handle_set_light_mode(hass: HomeAssistant, call: ServiceCall) -> None:
    coordinator = _get_coordinator(hass)
    light_num = int(call.data.get("light", 1))
    module = "light" if light_num == 1 else "light2"
    mode_label = call.data["mode"]
    mode_type = LIGHT_MODES.get(mode_label, 0)

    block = coordinator._build_config_block(module, {
        "modeType": mode_type,
        "lastAutoModeType": mode_type,
    })

    if "brightness" in call.data:
        block["mLevel"] = int(call.data["brightness"])
        block["mOnOff"] = 1

    if "schedule_start" in call.data or "schedule_end" in call.data:
        tp = block.get("timePeriod", [{"enabled": 1, "weekmask": 127}])
        if not tp:
            tp = [{"enabled": 1, "weekmask": 127}]
        if "schedule_start" in call.data:
            tp[0]["startTime"] = _time_to_seconds(call.data["schedule_start"])
        if "schedule_end" in call.data:
            tp[0]["endTime"] = _time_to_seconds(call.data["schedule_end"])
        if "brightness" in call.data:
            tp[0]["brightness"] = int(call.data["brightness"])
        tp[0].setdefault("enabled", 1)
        tp[0].setdefault("weekmask", 127)
        block["timePeriod"] = tp

    if "ppfd_target" in call.data:
        pp = block.get("ppfdPeriod", [{"enabled": 1, "weekmask": 127}])
        if not pp:
            pp = [{"enabled": 1, "weekmask": 127}]
        pp[0]["brightness"] = int(call.data["ppfd_target"])
        if "schedule_start" in call.data:
            pp[0]["startTime"] = _time_to_seconds(call.data["schedule_start"])
        if "schedule_end" in call.data:
            pp[0]["endTime"] = _time_to_seconds(call.data["schedule_end"])
        pp[0].setdefault("enabled", 1)
        pp[0].setdefault("weekmask", 127)
        block["ppfdPeriod"] = pp

    if "fade_minutes" in call.data:
        fade_seconds = int(call.data["fade_minutes"]) * 60
        if mode_type == LIGHT_MODES["PPFD"]:
            pp = block.get("ppfdPeriod", [{}])
            if pp:
                pp[0]["fadeTime"] = fade_seconds
        else:
            tp = block.get("timePeriod", [{}])
            if tp:
                tp[0]["fadeTime"] = fade_seconds

    if "dimming_min" in call.data:
        block["ppfdMinBrightness"] = int(call.data["dimming_min"])
    if "dimming_max" in call.data:
        block["ppfdMaxBrightness"] = int(call.data["dimming_max"])

    await coordinator.async_send_config_field(module, block)


async def async_handle_set_fan_mode(hass: HomeAssistant, call: ServiceCall) -> None:
    coordinator = _get_coordinator(hass)
    module = call.data.get("device", "fan")
    mode_label = call.data["mode"]
    mode_type = FAN_MODES.get(mode_label, 0)

    block = coordinator._build_config_block(module, {"modeType": mode_type})

    if "speed" in call.data:
        block["maxSpeed"] = int(call.data["speed"])
        block["mLevel"] = int(call.data["speed"])
    if "standby_speed" in call.data:
        block["minSpeed"] = int(call.data["standby_speed"])

    if "schedule_start" in call.data or "schedule_end" in call.data:
        tp = block.get("timePeriod", [{"enabled": 1, "weekmask": 127}])
        if not tp:
            tp = [{"enabled": 1, "weekmask": 127}]
        if "schedule_start" in call.data:
            tp[0]["startTime"] = _time_to_seconds(call.data["schedule_start"])
        if "schedule_end" in call.data:
            tp[0]["endTime"] = _time_to_seconds(call.data["schedule_end"])
        tp[0].setdefault("enabled", 1)
        tp[0].setdefault("weekmask", 127)
        block["timePeriod"] = tp

    if any(k in call.data for k in ("cycle_run_minutes", "cycle_off_minutes", "cycle_times")):
        ct = block.get("cycleTime", {"weekmask": 127})
        if "cycle_run_minutes" in call.data:
            ct["openDur"] = int(call.data["cycle_run_minutes"]) * 60
        if "cycle_off_minutes" in call.data:
            ct["closeDur"] = int(call.data["cycle_off_minutes"]) * 60
        if "cycle_times" in call.data:
            ct["times"] = int(call.data["cycle_times"])
        block["cycleTime"] = ct

    await coordinator.async_send_config_field(module, block)


async def async_handle_set_humidifier_mode(hass: HomeAssistant, call: ServiceCall) -> None:
    coordinator = _get_coordinator(hass)
    mode_label = call.data["mode"]
    mode_type = HUMIDIFIER_MODES.get(mode_label, 0)

    block = coordinator._build_config_block("humidifier", {"modeType": mode_type})

    if "schedule_start" in call.data or "schedule_end" in call.data:
        tp = block.get("timePeriod", [{"enabled": 1, "weekmask": 127}])
        if not tp:
            tp = [{"enabled": 1, "weekmask": 127}]
        if "schedule_start" in call.data:
            tp[0]["startTime"] = _time_to_seconds(call.data["schedule_start"])
        if "schedule_end" in call.data:
            tp[0]["endTime"] = _time_to_seconds(call.data["schedule_end"])
        tp[0].setdefault("enabled", 1)
        tp[0].setdefault("weekmask", 127)
        block["timePeriod"] = tp

    if any(k in call.data for k in ("cycle_run_minutes", "cycle_off_minutes", "cycle_times")):
        ct = block.get("cycleTime", {"weekmask": 127})
        if "cycle_run_minutes" in call.data:
            ct["openDur"] = int(call.data["cycle_run_minutes"]) * 60
        if "cycle_off_minutes" in call.data:
            ct["closeDur"] = int(call.data["cycle_off_minutes"]) * 60
        if "cycle_times" in call.data:
            ct["times"] = int(call.data["cycle_times"])
        block["cycleTime"] = ct

    await coordinator.async_send_config_field("humidifier", block)


def async_register_services(hass: HomeAssistant) -> None:
    """Register all spider_farmer_ggs services."""
    hass.services.async_register(
        DOMAIN, "set_light_mode",
        lambda call: async_handle_set_light_mode(hass, call),
    )
    hass.services.async_register(
        DOMAIN, "set_fan_mode",
        lambda call: async_handle_set_fan_mode(hass, call),
    )
    hass.services.async_register(
        DOMAIN, "set_humidifier_mode",
        lambda call: async_handle_set_humidifier_mode(hass, call),
    )
