"""Service handlers for Spider Farmer GGS Controller."""
from __future__ import annotations

import datetime
import functools
import json
import logging
from datetime import time as dt_time

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, FAN_MODES, HUMIDIFIER_MODES, LIGHT_MODES, PLAN_STORAGE_PATH
from .coordinator import SpiderFarmerGGSCoordinator
from . import plan_storage
from . import stage as stage_lib

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


async def async_handle_deploy_stage(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Write a preset to the controller as the active planting stage."""
    coordinator = _get_coordinator(hass)
    name = call.data["preset"]

    body = plan_storage.get_preset(PLAN_STORAGE_PATH, name)
    if body is None:
        raise ValueError(f"No preset named {name!r}")

    start = call.data["start_date"]
    end = call.data["end_date"]
    if isinstance(start, str):
        start = datetime.date.fromisoformat(start)
    if isinstance(end, str):
        end = datetime.date.fromisoformat(end)

    existing = await coordinator.async_read_stage()
    if existing is None:
        raise HomeAssistantError("Could not read the current stage from the controller")

    stage_id = stage_lib.get_field(existing, "stageId") or int(
        datetime.datetime.now().timestamp()
    )
    new_stage = stage_lib.build_stage(
        body, name.capitalize(), start, end, stage_id, existing=existing
    )

    await coordinator.async_probe({
        "method": "setConfigField",
        "params": {"keyPath": ["plan", "stage"], "stage": [new_stage]},
    }, wait=5)

    # Entities cache values, so read the stage back rather than trusting them.
    written = await coordinator.async_read_stage()
    if written is None:
        raise HomeAssistantError("Deployed, but could not read the stage back to confirm")
    check = stage_lib.parse_stage(written)
    if check["label"] != name.capitalize() or check["start_date"] != start:
        raise HomeAssistantError(
            f"Stage did not land: controller reports {check['label']!r} "
            f"starting {check['start_date']}"
        )

    if call.data.get("set_device_modes"):
        await _set_plan_following_modes(coordinator)

    await coordinator.async_request_refresh()
    return {
        "label": check["label"],
        "start_date": check["start_date"].isoformat(),
        "end_date": check["end_date"].isoformat() if check["end_date"] else None,
    }


async def _set_plan_following_modes(coordinator) -> None:
    """Point the devices at the plan: light to PPFD, air devices to environment."""
    await coordinator.async_send_config_field(
        "light", coordinator._build_config_block("light", {"modeType": LIGHT_MODES["PPFD"]})
    )
    for module in ("fan", "blower", "humidifier"):
        await coordinator.async_send_config_field(
            module,
            coordinator._build_config_block(
                module, {"modeType": FAN_MODES["Environment: Temperature & humidity"]}
            ),
        )


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
        DOMAIN, "deploy_stage",
        functools.partial(async_handle_deploy_stage, hass),
        supports_response=SupportsResponse.ONLY,
    )
