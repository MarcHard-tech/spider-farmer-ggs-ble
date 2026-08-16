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
from .coordinator import SpiderFarmerGGSCoordinator, _is_config_block
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


def _coerce_stage_date(value, field_name: str) -> datetime.date:
    """Normalise a service-call date field to a plain date, or raise clearly.

    Accepts a date, a datetime (its .date() is used), or an ISO date string.
    Anything else - missing, an int, a bad string, etc. - raises HomeAssistantError
    here instead of failing deep inside stage.py with a confusing TypeError or
    AttributeError once the value is already being packed for the controller.
    """
    if value is None:
        raise HomeAssistantError(f"{field_name} is required")
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str):
        try:
            return datetime.date.fromisoformat(value)
        except ValueError as exc:
            raise HomeAssistantError(
                f"{field_name} must be an ISO date (YYYY-MM-DD), got {value!r}"
            ) from exc
    raise HomeAssistantError(
        f"{field_name} must be a date, got {type(value).__name__}: {value!r}"
    )


# Proven against the live controller 2026-08-16 (see task-18-brief.md):
# index keyPath writes like ["plan","stage",0,"label"] are acknowledged with
# code=200 but silently ignored - a 200 is never proof a write landed. Only the
# array form at ["plan","stage"] actually applies, and it REPLACES the element
# rather than merging, so every write must carry the complete stage element.
# Light blocks are excluded here on size grounds: the full stage including both
# light blocks is 977 bytes, over the ~512-byte BLE attribute limit, while the
# stage without light blocks is 410 bytes. Lights are written separately to
# ["device","light"]/["device","light2"] by _write_stage_lights.
_STAGE_ELEMENT_FIELDS = (
    "stageId", "label", "startDate", "endDate", "alarmDate", "color", "target",
)
_MAX_COMMAND_BYTES = 480


def _check_ack(replies: list[dict], what: str) -> None:
    """Raise unless replies contain a setConfigField reply with code == 200.

    The controller streams unsolicited status messages every few seconds, so
    async_probe's result can include replies unrelated to the command just
    sent - position can't be trusted, only a matching method+code can. Success
    is any reply with method == setConfigField AND code == 200 - checking only
    the first setConfigField reply would let an unrelated/echoed non-200 reply
    report a genuinely successful write as a failure.
    """
    setconfig_replies = [r for r in replies if r.get("method") == "setConfigField"]
    if any(r.get("code") == 200 for r in setconfig_replies):
        return
    if not setconfig_replies:
        reason = "no matching reply"
    else:
        reason = f"code={setconfig_replies[0].get('code')}"
    raise HomeAssistantError(f"{what} was not acknowledged by the controller ({reason}).")


async def _write_stage(coordinator, stage_obj: dict) -> None:
    """Write a stage to the controller as a single array-form setConfigField.

    Builds the complete stage element (identity + target, no light blocks - see
    module docstring above) and sends it as ["plan","stage"] <- [element], the
    only keyPath proven to actually apply on this device.
    """
    element = {k: stage_obj[k] for k in _STAGE_ELEMENT_FIELDS if k in stage_obj}
    cmd = {
        "method": "setConfigField",
        "params": {"keyPath": ["plan", "stage"], "stage": [element]},
    }
    size = len(json.dumps(cmd, separators=(",", ":")).encode())
    if size > _MAX_COMMAND_BYTES:
        raise HomeAssistantError(
            f"Cannot write stage: command is {size} bytes, over the "
            f"{_MAX_COMMAND_BYTES}-byte limit."
        )

    replies = await coordinator.async_probe(cmd, wait=4)
    _check_ack(replies, "Stage write")


async def _write_stage_lights(coordinator, preset: dict) -> None:
    """Apply the preset's light1/light2 blocks to the live light modules.

    Writes to ["device","<module>"] REPLACE the module's config, exactly like
    the stage write above, so the preset's block is never sent alone - it is
    merged over the module's current config first. Sending a bare block strips
    the module's other settings; this is how the fan's cycleTime and maxSpeed
    were lost on 2026-08-16. Raises HomeAssistantError naming the module on any
    failure - unreadable current config, oversize command, or a missing/failed
    acknowledgement.
    """
    for light_key, module in (("light1", "light"), ("light2", "light2")):
        preset_block = preset.get(light_key)
        if not isinstance(preset_block, dict):
            continue

        read_cmd = {
            "method": "getConfigField",
            "params": {"keyPath": ["device", module]},
        }
        # async_probe also returns unsolicited getDevSta pushes, which carry
        # data[module] as the cut-down runtime view ({"modeType","level",...}),
        # not the full config. Merging that over the preset block and writing
        # it would strip mLevel/timePeriod/ppfdPeriod/etc - the same mechanism
        # that destroyed the fan's cycleTime and maxSpeed on 2026-08-16. So
        # every reply is checked, and a candidate is only accepted once
        # _is_config_block confirms it is a real config block, not a runtime
        # push that merely happens to contain the module key.
        read_replies = await coordinator.async_probe(read_cmd, wait=5)
        current = None
        for reply in read_replies:
            data = reply.get("data") or {}
            candidate = data.get(module)
            if isinstance(candidate, dict) and _is_config_block(candidate):
                current = candidate
                break
        if not isinstance(current, dict):
            raise HomeAssistantError(
                f"Could not read the current config for {module!r} - stage was "
                "already written, but its lights were not applied."
            )

        merged = dict(current)
        merged.update(preset_block)

        write_cmd = {
            "method": "setConfigField",
            "params": {"keyPath": ["device", module], module: merged},
        }
        size = len(json.dumps(write_cmd, separators=(",", ":")).encode())
        if size > _MAX_COMMAND_BYTES:
            raise HomeAssistantError(
                f"Cannot write {module!r} lights: command is {size} bytes, over "
                f"the {_MAX_COMMAND_BYTES}-byte limit. Stage was already written."
            )

        write_replies = await coordinator.async_probe(write_cmd, wait=4)
        try:
            _check_ack(write_replies, f"Light write for {module!r}")
        except HomeAssistantError as exc:
            raise HomeAssistantError(f"{exc} Stage was already written.") from exc


async def async_handle_deploy_stage(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Write a preset to the controller as the active planting stage."""
    coordinator = _get_coordinator(hass)
    name = call.data["preset"]

    body = plan_storage.get_preset(PLAN_STORAGE_PATH, name)
    if body is None:
        raise ValueError(f"No preset named {name!r}")

    start = _coerce_stage_date(call.data.get("start_date"), "start_date")
    end = _coerce_stage_date(call.data.get("end_date"), "end_date")

    existing = await coordinator.async_read_stage()
    if existing is None:
        raise HomeAssistantError("Could not read the current stage from the controller")

    stage_id = stage_lib.get_field(existing, "stageId") or int(
        datetime.datetime.now().timestamp()
    )
    new_stage = stage_lib.build_stage(
        body, name.capitalize(), start, end, stage_id, existing=existing
    )

    await _write_stage(coordinator, new_stage)

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

    if call.data.get("set_lights", True):
        await _write_stage_lights(coordinator, body)

    if call.data.get("set_device_modes"):
        await _set_plan_following_modes(coordinator)

    await coordinator.async_request_refresh()
    return {
        "label": check["label"],
        "start_date": check["start_date"].isoformat(),
        "end_date": check["end_date"].isoformat() if check["end_date"] else None,
    }


async def _set_plan_following_modes(coordinator) -> None:
    """Point the devices at the plan: light to PPFD, air devices to environment.

    _build_config_block falls back to a bare {"modeType": ...} payload when a
    module's cache is still empty (e.g. before the first full poll). Sending that
    bare payload as a full config block wipes the module's schedule/cycle settings
    on the controller - seen happening for real on 2026-08-16. So each block is
    checked with _is_config_block before it is sent; anything that fails the check
    is skipped, and the caller is told loudly rather than silently left thinking
    the tent is following the plan when it is not.
    """
    overrides_by_module = {
        "light": {"modeType": LIGHT_MODES["PPFD"]},
        "fan": {"modeType": FAN_MODES["Environment: Temperature & humidity"]},
        "blower": {"modeType": FAN_MODES["Environment: Temperature & humidity"]},
        "humidifier": {"modeType": FAN_MODES["Environment: Temperature & humidity"]},
    }

    unsafe_modules = []
    for module, overrides in overrides_by_module.items():
        block = coordinator._build_config_block(module, overrides)
        if not _is_config_block(block):
            unsafe_modules.append(module)
            continue
        await coordinator.async_send_config_field(module, block)

    if unsafe_modules:
        raise HomeAssistantError(
            "Stage was deployed, but device modes were NOT set for: "
            f"{', '.join(unsafe_modules)} — their cached config is not populated "
            "yet (this happens before the integration's first full poll, or if "
            "poll_commands.json is missing). Wait for the integration to poll the "
            "controller, then retry deploy_stage with set_device_modes."
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


async def async_handle_manage_presets(hass: HomeAssistant, call: ServiceCall) -> dict:
    """List, save or delete stage presets. Always returns the full library."""
    action = call.data.get("action", "list")
    name = call.data.get("name")

    def _work() -> dict:
        if action == "save":
            if not name:
                raise HomeAssistantError("name is required to save a preset")
            body = call.data.get("body")
            if isinstance(body, str):
                try:
                    body = json.loads(body)
                except json.JSONDecodeError as exc:
                    raise HomeAssistantError(f"body must be valid JSON: {exc}") from exc
            if not isinstance(body, dict):
                raise HomeAssistantError("body must be a JSON object")
            if "target" not in body:
                raise HomeAssistantError(
                    "body must include a 'target' key - a preset without one "
                    "would only be caught later, at deploy time, when it could "
                    "mis-set a live grow tent"
                )
            plan_storage.save_preset(PLAN_STORAGE_PATH, name, body)
        elif action == "delete":
            if not name:
                raise HomeAssistantError("name is required to delete a preset")
            plan_storage.delete_preset(PLAN_STORAGE_PATH, name)
        elif action != "list":
            raise HomeAssistantError(f"unknown action {action!r}")
        # A single consistent read, not list_presets() + get_preset() per name -
        # the latter re-reads the file each call and can race a concurrent
        # save/delete, producing a null entry the dashboard would choke on.
        return plan_storage.list_all(PLAN_STORAGE_PATH)

    return {"presets": await hass.async_add_executor_job(_work)}


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
    hass.services.async_register(
        DOMAIN, "manage_presets",
        functools.partial(async_handle_manage_presets, hass),
        supports_response=SupportsResponse.ONLY,
    )
