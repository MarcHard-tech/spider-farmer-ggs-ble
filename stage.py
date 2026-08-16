"""Pure helpers for the GGS planting stage payload.

Deliberately free of Home Assistant imports and relative imports so it can be
imported and unit-tested standalone. Keep it that way.
"""
from __future__ import annotations

import copy
import datetime
import difflib
import re


def pack_date(d: datetime.date) -> int:
    """Pack a date the way the controller stores stage dates."""
    return (d.year << 16) | (d.month << 8) | d.day


def unpack_date(value: int) -> datetime.date:
    """Inverse of pack_date."""
    return datetime.date((value >> 16) & 0xFFFF, (value >> 8) & 0xFF, value & 0xFF)


_NORMALISE = re.compile(r"[^a-z0-9]")


def _normalise(key: str) -> str:
    return _NORMALISE.sub("", key.lower())


def get_field(block: dict, key: str, default=None):
    """Look up a key, tolerating BLE-corrupted key names.

    Packet boundaries land mid-key, producing things like "ppfdMaxBrightne? ss"
    or "enableld". Exact match first, then normalised, then a close match.
    Returns default if block is not a dict.
    """
    if not isinstance(block, dict):
        return default

    if key in block:
        return block[key]

    want = _normalise(key)
    normalised = {_normalise(k): k for k in block}
    if want in normalised:
        return block[normalised[want]]

    close = difflib.get_close_matches(want, list(normalised), n=1, cutoff=0.85)
    if close:
        return block[normalised[close[0]]]
    return default


def _maybe_date(value):
    if not isinstance(value, int) or value <= 0:
        return None
    try:
        return unpack_date(value)
    except ValueError:
        return None


def parse_stage(stage_obj: dict) -> dict:
    """Flatten a controller stage object into plain values.

    Returns all 15 keys with None values if stage_obj is not a dict.
    Never raises on malformed input.
    """
    if not isinstance(stage_obj, dict):
        return {
            "label": None,
            "stage_id": None,
            "start_date": None,
            "end_date": None,
            "day_start": None,
            "day_end": None,
            "temp_day": None,
            "temp_night": None,
            "temp_deadband": None,
            "humi_day": None,
            "humi_night": None,
            "humi_deadband": None,
            "co2_day": None,
            "co2_night": None,
            "co2_deadband": None,
        }

    target = get_field(stage_obj, "target", {}) or {}
    day = get_field(target, "dayTime", {}) or {}
    temp = get_field(target, "temp", {}) or {}
    humi = get_field(target, "humi", {}) or {}
    co2 = get_field(target, "co2", {}) or {}

    return {
        "label": get_field(stage_obj, "label"),
        "stage_id": get_field(stage_obj, "stageId"),
        "start_date": _maybe_date(get_field(stage_obj, "startDate")),
        "end_date": _maybe_date(get_field(stage_obj, "endDate")),
        "day_start": get_field(day, "startTime"),
        "day_end": get_field(day, "endTime"),
        "temp_day": get_field(temp, "targetDay"),
        "temp_night": get_field(temp, "targetNight"),
        "temp_deadband": get_field(temp, "deadband"),
        "humi_day": get_field(humi, "targetDay"),
        "humi_night": get_field(humi, "targetNight"),
        "humi_deadband": get_field(humi, "deadband"),
        "co2_day": get_field(co2, "targetDay"),
        "co2_night": get_field(co2, "targetNight"),
        "co2_deadband": get_field(co2, "deadband"),
    }


def build_stage(preset: dict, label: str, start: datetime.date,
                end: datetime.date, stage_id: int,
                existing: dict | None = None) -> dict:
    """Build a full stage object ready to write to the controller.

    `existing` is the stage currently on the controller. Fields it owns and we
    have no business inventing — alarmDate, color, and light2 when the preset
    does not define one — are carried across.
    """
    if end < start:
        raise ValueError(f"end date {end} is before start date {start}")

    body = copy.deepcopy(preset)
    existing = existing or {}

    body["label"] = label
    body["stageId"] = stage_id
    body["startDate"] = pack_date(start)
    body["endDate"] = pack_date(end)

    for field in ("alarmDate", "color"):
        value = get_field(existing, field)
        if value is not None:
            body[field] = value

    # Deliberately does NOT carry `existing["light2"]` across: the element
    # actually written to the controller is filtered to
    # _STAGE_ELEMENT_FIELDS in services.py, which does not include "light2",
    # and light modules are written separately (services._prepare_stage_lights/
    # _send_stage_lights) from the raw preset body, never from this built
    # stage. A light2 carry-over here was unreachable dead code - removed
    # 2026-08-16.

    return body
