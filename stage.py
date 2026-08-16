"""Pure helpers for the GGS planting stage payload.

Deliberately free of Home Assistant imports and relative imports so it can be
imported and unit-tested standalone. Keep it that way.
"""
from __future__ import annotations

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
    """
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
