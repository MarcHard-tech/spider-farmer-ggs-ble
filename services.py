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
# ["device","light"]/["device","light2"] by _prepare_stage_lights/_send_stage_lights.
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


def _build_stage_command(stage_obj: dict) -> dict:
    """Build the array-form setConfigField command for a stage, size-checked.

    Builds the complete stage element (identity + target, no light blocks - see
    module docstring above) addressed at ["plan","stage"] <- [element], the
    only keyPath proven to actually apply on this device. Building and
    size-checking is split from sending (see _write_stage) so the whole deploy
    - stage AND lights - can be validated before anything is written; see
    _prepare_stage_lights for why that matters.
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
    return cmd


async def _write_stage(coordinator, cmd: dict) -> None:
    """Send an already-built, already size-checked stage setConfigField command."""
    replies = await coordinator.async_probe(cmd, wait=4)
    _check_ack(replies, "Stage write")


async def _prepare_stage_lights(coordinator, preset: dict) -> list[dict]:
    """Read current light config and build+size-check the merged write commands.

    Deliberately does not write anything - only reads (side-effect-free) and
    builds. Deploy is not atomic: once the stage write lands it cannot be
    undone, so every command - stage AND lights - must be built and
    size-checked BEFORE any of them are sent. Previously the light command's
    size check ran after the stage was already written, so an oversized light
    payload would abort the deploy in the worst order: stage changed, lights
    not applied, tent left in a mismatched state.

    Returns one entry per light the preset defines:
    {"module", "write_cmd", "preset_block", "read_cmd"}. Raises
    HomeAssistantError naming the module if its current config can't be read
    or the built command is oversize.
    """
    prepared: list[dict] = []
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
                f"Could not read the current config for {module!r} - aborting "
                "before anything is written."
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
                f"the {_MAX_COMMAND_BYTES}-byte limit - aborting before anything "
                "is written."
            )

        prepared.append({
            "module": module,
            "write_cmd": write_cmd,
            "preset_block": preset_block,
            "read_cmd": read_cmd,
        })
    return prepared


async def _send_stage_lights(coordinator, prepared: list[dict]) -> None:
    """Send prepared light writes, then read each back to confirm it landed.

    A code=200 ack is not proof a write landed - indexed stage writes returned
    200 and were silently ignored (see module docstring above). The stage
    write is read back and compared; this does the same for the light write,
    which changes the tent's live photoperiod. stage_lib.get_field is used for
    the comparison because BLE can corrupt key names in what the controller
    echoes back (see stage.py), so a plain dict.get would false-negative on a
    write that actually landed.
    """
    for item in prepared:
        module = item["module"]
        write_replies = await coordinator.async_probe(item["write_cmd"], wait=4)
        try:
            _check_ack(write_replies, f"Light write for {module!r}")
        except HomeAssistantError as exc:
            raise HomeAssistantError(f"{exc} Stage was already written.") from exc

        verify_replies = await coordinator.async_probe(item["read_cmd"], wait=5)
        verified = None
        for reply in verify_replies:
            data = reply.get("data") or {}
            candidate = data.get(module)
            if isinstance(candidate, dict) and _is_config_block(candidate):
                verified = candidate
                break
        if verified is None:
            raise HomeAssistantError(
                f"Light write for {module!r} was acknowledged, but its config "
                "could not be read back to confirm. Stage was already written."
            )

        _MISSING = object()
        mismatched = [
            key for key, value in item["preset_block"].items()
            if stage_lib.get_field(verified, key, _MISSING) != value
        ]
        if mismatched:
            raise HomeAssistantError(
                f"Light write for {module!r} did not land: {', '.join(mismatched)} "
                "do not match what was sent. Stage was already written."
            )


async def async_handle_deploy_stage(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Write a preset to the controller as the active planting stage."""
    coordinator = _get_coordinator(hass)
    name = call.data["preset"]

    body = plan_storage.get_preset(PLAN_STORAGE_PATH, name)
    if body is None:
        raise HomeAssistantError(f"No preset named {name!r}")

    start = _coerce_stage_date(call.data.get("start_date"), "start_date")
    end = _coerce_stage_date(call.data.get("end_date"), "end_date")

    existing = await coordinator.async_read_stage()
    if existing is None:
        raise HomeAssistantError("Could not read the current stage from the controller")

    # stageId 0 is a legitimate id - `or` would treat it as falsy and
    # renumber it to a new timestamp on every deploy.
    existing_stage_id = stage_lib.get_field(existing, "stageId")
    stage_id = (
        existing_stage_id if existing_stage_id is not None
        else int(datetime.datetime.now().timestamp())
    )
    new_stage = stage_lib.build_stage(
        body, name.capitalize(), start, end, stage_id, existing=existing
    )

    # Build and size-check EVERYTHING - the stage command and any light
    # commands - before sending anything. Deploy is not atomic: once the
    # stage write lands it can't be undone, so an oversized light payload
    # must abort here, not after the stage has already changed.
    stage_cmd = _build_stage_command(new_stage)
    prepared_lights = []
    if call.data.get("set_lights", True):
        prepared_lights = await _prepare_stage_lights(coordinator, body)

    await _write_stage(coordinator, stage_cmd)

    # Entities cache values, so read the stage back rather than trusting them.
    written = await coordinator.async_read_stage()
    if written is None:
        raise HomeAssistantError("Deployed, but could not read the stage back to confirm")
    check = stage_lib.parse_stage(written)
    if (
        check["label"] != name.capitalize()
        or check["start_date"] != start
        or check["end_date"] != end
    ):
        raise HomeAssistantError(
            f"Stage did not land: controller reports {check['label']!r} "
            f"starting {check['start_date']}, ending {check['end_date']}"
        )

    if prepared_lights:
        await _send_stage_lights(coordinator, prepared_lights)

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

    async_send_config_field is the single choke point that refuses a bare
    {"modeType": ...} payload when a module's cache is still empty (e.g. before
    the first full poll) - sending that as a full config block would wipe the
    module's schedule/cycle settings on the controller, which really happened
    to the fan on this device. That guard raises HomeAssistantError; it is
    caught here per-module so one module's empty cache does not stop the
    others, and the caller is told loudly which modules were skipped rather
    than silently left thinking the tent is following the plan when it isn't.
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
        try:
            await coordinator.async_send_config_field(module, block)
        except HomeAssistantError:
            unsafe_modules.append(module)

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

    # raw_hex replaces command entirely: the bytes go to the characteristic
    # untouched, so a frame captured from the vendor app can be replayed exactly.
    raw_hex = call.data.get("raw_hex")
    command = {}
    raw_bytes = None
    if raw_hex:
        try:
            raw_bytes = bytes.fromhex("".join(str(raw_hex).split()))
        except ValueError as exc:
            raise HomeAssistantError(f"raw_hex must be hex: {exc}") from exc
    else:
        raw = call.data["command"]
        try:
            command = json.loads(raw) if isinstance(raw, str) else dict(raw)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise HomeAssistantError(f"command must be a JSON object: {exc}") from exc
        if not isinstance(command, dict):
            raise HomeAssistantError("command must be a JSON object, e.g. {\"method\": \"getSysSta\"}")

    wait = float(call.data.get("wait", 3))

    # Transport overrides, diagnostic only. Omitted fields keep the values the
    # controller's own packets use, so an ordinary call behaves as before.
    transport = {}
    if raw_bytes is not None:
        transport["raw_bytes"] = raw_bytes
    if "max_chunk" in call.data:
        transport["max_chunk"] = int(call.data["max_chunk"])
    if "msg_id" in call.data:
        transport["msg_id"] = int(call.data["msg_id"]) & 0xFFFF
    if call.data.get("characteristic"):
        transport["characteristic"] = str(call.data["characteristic"])
    if "write_without_response" in call.data:
        transport["response"] = not bool(call.data["write_without_response"])
    if "version" in call.data:
        transport["version"] = int(call.data["version"])

    _LOGGER.warning(
        "GGS send_raw_command: %s%s",
        raw_bytes.hex() if raw_bytes is not None else json.dumps(command),
        f" transport={ {k: v for k, v in transport.items() if k != 'raw_bytes'} }"
        if transport else "",
    )
    replies = await coordinator.async_probe(command, wait, **transport)
    _LOGGER.warning(
        "GGS send_raw_command got %d repl%s: %s",
        len(replies), "y" if len(replies) == 1 else "ies",
        json.dumps(replies)[:2000],
    )
    return {"count": len(replies), "replies": replies}


async def async_handle_dump_gatt(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Return the controller's GATT characteristics. Read-only."""
    coordinator = _get_coordinator(hass)
    info = await coordinator.async_dump_gatt()
    _LOGGER.warning("GGS dump_gatt: %s", json.dumps(info))
    chars = info["characteristics"]
    info["writable"] = [
        c["characteristic"] for c in chars
        if {"write", "write-without-response"} & set(c["properties"])
    ]
    info["count"] = len(chars)
    return info


_REQUIRED_TARGET_SECTIONS = ("dayTime", "temp", "humi", "co2")
_REQUIRED_TARGET_SUBFIELDS = ("targetDay", "targetNight", "deadband")


def _validate_preset_target(body: dict) -> None:
    """Require a preset's target block to be complete, not merely present.

    The stage array write REPLACES the element, so deploying a preset with an
    empty or partial target (e.g. {"target": {}}) erases every temperature,
    humidity and CO2 setpoint on a live tent - and the deploy's read-back only
    checks label/start/end date, so it would still report success. Catch it
    here, at save time, instead.
    """
    target = body.get("target")
    if not isinstance(target, dict):
        raise HomeAssistantError("body.target must be an object")

    missing = [k for k in _REQUIRED_TARGET_SECTIONS if k not in target]
    for section in ("temp", "humi", "co2"):
        group = target.get(section)
        if not isinstance(group, dict):
            if section not in missing:
                missing.append(section)
            continue
        for sub in _REQUIRED_TARGET_SUBFIELDS:
            if sub not in group:
                missing.append(f"{section}.{sub}")

    if missing:
        raise HomeAssistantError(
            "body.target is missing required field(s): "
            f"{', '.join(missing)} - saving would let a deploy erase those "
            "targets on a live tent"
        )


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
            _validate_preset_target(body)
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
        DOMAIN, "dump_gatt",
        functools.partial(async_handle_dump_gatt, hass),
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
