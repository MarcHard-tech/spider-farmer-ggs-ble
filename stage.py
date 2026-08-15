"""Pure helpers for the GGS planting stage payload.

Deliberately free of Home Assistant imports and relative imports so it can be
imported and unit-tested standalone. Keep it that way.
"""
from __future__ import annotations

import datetime


def pack_date(d: datetime.date) -> int:
    """Pack a date the way the controller stores stage dates."""
    return (d.year << 16) | (d.month << 8) | d.day


def unpack_date(value: int) -> datetime.date:
    """Inverse of pack_date."""
    return datetime.date((value >> 16) & 0xFFFF, (value >> 8) & 0xFF, value & 0xFF)
