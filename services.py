"""Service handlers for Spider Farmer GGS Controller."""
from __future__ import annotations

import functools
import json
import logging
from datetime import time as dt_time

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse

from .const import DOMAIN, FAN_MODES, HUMIDIFIER_MODES, LIGHT_MODES
from .coordinator import SpiderFarmerGGSCoordinator
from . import plan_storage

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


def _build_plan_data(call_data: dict) -> dict:
    """Build a plan data dict from service call data."""
    plan = {"name": call_data["name"]}

    if "day_cycle_start" in call_data:
        plan["day_cycle"] = {
            "start": str(call_data["day_cycle_start"]),
            "end": str(call_data.get("day_cycle_end", "06:00")),
        }

    for section, fields in [
        ("temperature", ("temp_day", "temp_night", "temp_dead_zone")),
        ("humidity", ("humidity_day", "humidity_night", "humidity_dead_zone")),
        ("co2", ("co2_day", "co2_night", "co2_dead_zone")),
    ]:
        day_key, night_key, dz_key = fields
        if day_key in call_data:
            plan[section] = {
                "day": call_data[day_key],
                "night": call_data.get(night_key, call_data[day_key]),
                "dead_zone": call_data.get(dz_key, 3),
            }

    if "light1_ppfd_target" in call_data:
        plan["light1"] = {
            "start": str(call_data.get("day_cycle_start", "18:00")),
            "end": str(call_data.get("day_cycle_end", "06:00")),
            "ppfd_target": call_data["light1_ppfd_target"],
            "dimming_min": call_data.get("light1_dimming_min", 10),
            "dimming_max": call_data.get("light1_dimming_max", 100),
            "fade_minutes": call_data.get("light1_fade_minutes", 30),
            "dim_threshold": 0,
            "off_threshold": 0,
        }

    if "start_date" in call_data:
        plan["start_date"] = str(call_data["start_date"])
    if "end_date" in call_data:
        plan["end_date"] = str(call_data["end_date"])

    return plan


async def async_handle_create_plan(hass: HomeAssistant, call: ServiceCall) -> None:
    plan_data = _build_plan_data(call.data)
    plan_storage.save_plan(call.data["name"], plan_data)


async def async_handle_update_plan(hass: HomeAssistant, call: ServiceCall) -> None:
    name = call.data["name"]
    existing = plan_storage.get_plan(name)
    if not existing:
        _LOGGER.error("Plan not found: %s", name)
        return
    updates = _build_plan_data(call.data)
    for key, value in updates.items():
        if key != "name" and value is not None:
            if isinstance(existing.get(key), dict) and isinstance(value, dict):
                existing[key].update(value)
            else:
                existing[key] = value
    plan_storage.save_plan(name, existing)


async def async_handle_delete_plan(hass: HomeAssistant, call: ServiceCall) -> None:
    if not plan_storage.delete_plan(call.data["name"]):
        _LOGGER.warning("Plan not found: %s", call.data["name"])


async def async_handle_activate_plan(hass: HomeAssistant, call: ServiceCall) -> None:
    coordinator = _get_coordinator(hass)
    name = call.data["name"]
    plan = plan_storage.get_plan(name)
    if not plan:
        _LOGGER.error("Plan not found: %s", name)
        return

    # Override dates if provided
    if "start_date" in call.data:
        plan["start_date"] = str(call.data["start_date"])
    if "end_date" in call.data:
        plan["end_date"] = str(call.data["end_date"])

    # Send light 1 config
    light1 = plan.get("light1", {})
    if light1:
        light_block = coordinator._build_config_block("light", {
            "modeType": 12,  # PPFD mode
            "lastAutoModeType": 12,
            "mOnOff": 1,
            "ppfdPeriod": [{
                "enabled": 1,
                "weekmask": 127,
                "startTime": _time_to_seconds(light1.get("start", "18:00")),
                "endTime": _time_to_seconds(light1.get("end", "06:00")),
                "brightness": light1.get("ppfd_target", 200),
                "fadeTime": light1.get("fade_minutes", 30) * 60,
            }],
            "ppfdMinBrightness": light1.get("dimming_min", 10),
            "ppfdMaxBrightness": light1.get("dimming_max", 100),
            "darkTemp": light1.get("dim_threshold", 0),
            "offTemp": light1.get("off_threshold", 0),
        })
        await coordinator.async_send_config_field("light", light_block)

    # Send light 2 config if present
    light2 = plan.get("light2", {})
    if light2:
        light2_block = coordinator._build_config_block("light2", {
            "modeType": 12,
            "lastAutoModeType": 12,
            "mOnOff": 1,
            "ppfdPeriod": [{
                "enabled": 1,
                "weekmask": 127,
                "startTime": _time_to_seconds(light2.get("start", "18:00")),
                "endTime": _time_to_seconds(light2.get("end", "06:00")),
                "brightness": light2.get("ppfd_target", 200),
                "fadeTime": light2.get("fade_minutes", 30) * 60,
            }],
            "ppfdMinBrightness": light2.get("dimming_min", 10),
            "ppfdMaxBrightness": light2.get("dimming_max", 100),
        })
        await coordinator.async_send_config_field("light2", light2_block)

    plan_storage.set_active_plan(name)
    _LOGGER.info("Activated planting plan: %s", name)


async def async_handle_deactivate_plan(hass: HomeAssistant, call: ServiceCall) -> None:
    plan_storage.set_active_plan(None)
    _LOGGER.info("Deactivated planting plan")


async def async_handle_send_raw_command(
    hass: HomeAssistant, call: ServiceCall
) -> dict:
    """Send an arbitrary JSON command to the controller and return the replies.

    A diagnostic tool for working out protocol commands the integration does not
    support yet. It writes straight to the device, so a malformed command can
    change settings — read before writing.
    """
    coordinator = _get_coordinator(hass)
    raw = call.data["command"]
    try:
        command = json.loads(raw) if isinstance(raw, str) else dict(raw)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise ValueError(f"command must be a JSON object: {exc}") from exc
    if not isinstance(command, dict):
        raise ValueError("command must be a JSON object, e.g. {\"method\": \"getSysSta\"}")

    wait = float(call.data.get("wait", 3))
    _LOGGER.warning("GGS send_raw_command: %s", json.dumps(command))
    replies = await coordinator.async_probe(command, wait)
    _LOGGER.warning(
        "GGS send_raw_command got %d repl%s: %s",
        len(replies), "y" if len(replies) == 1 else "ies",
        json.dumps(replies)[:2000],
    )
    return {"count": len(replies), "replies": replies}


def async_register_services(hass: HomeAssistant) -> None:
    """Register all spider_farmer_ggs services."""
    hass.services.async_register(
        DOMAIN, "send_raw_command",
        functools.partial(async_handle_send_raw_command, hass),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN, "set_light_mode",
        functools.partial(async_handle_set_light_mode, hass),
    )
    hass.services.async_register(
        DOMAIN, "set_fan_mode",
        functools.partial(async_handle_set_fan_mode, hass),
    )
    hass.services.async_register(
        DOMAIN, "set_humidifier_mode",
        functools.partial(async_handle_set_humidifier_mode, hass),
    )
    hass.services.async_register(
        DOMAIN, "create_plan",
        functools.partial(async_handle_create_plan, hass),
    )
    hass.services.async_register(
        DOMAIN, "update_plan",
        functools.partial(async_handle_update_plan, hass),
    )
    hass.services.async_register(
        DOMAIN, "delete_plan",
        functools.partial(async_handle_delete_plan, hass),
    )
    hass.services.async_register(
        DOMAIN, "activate_plan",
        functools.partial(async_handle_activate_plan, hass),
    )
    hass.services.async_register(
        DOMAIN, "deactivate_plan",
        functools.partial(async_handle_deactivate_plan, hass),
    )
