"""Built-in planting stage presets.

Settings only — dates and stageId are supplied at deploy time. Values are
starting points anchored on the controller's original Seed stage, not
horticultural gospel; the grower edits them from the dashboard.

No Home Assistant imports and no relative imports: this module is unit-tested
standalone.
"""
from __future__ import annotations

DAY_START = 64800   # 18:00
DAY_END = 36000     # 10:00
LIGHT_FADE = 1800   # 30 min sunrise/sunset simulation
PPFD_MODE = 12


def _stage(temp, humi, co2, ppfd, day_end=DAY_END):
    """Build a preset body. temp/humi/co2 are (day, night, deadband)."""
    return {
        "target": {
            "dayTime": {"startTime": DAY_START, "endTime": 28800},
            "temp": {"targetDay": temp[0], "targetNight": temp[1], "deadband": temp[2]},
            "humi": {"targetDay": humi[0], "targetNight": humi[1], "deadband": humi[2]},
            "co2": {"targetDay": co2[0], "targetNight": co2[1], "deadband": co2[2]},
        },
        "light1": {
            "modeType": PPFD_MODE,
            "ppfdMinBrightness": 11,
            "ppfdMaxBrightness": 100,
            "ppfdPeriod": [{
                "enabled": 1, "weekmask": 127,
                "startTime": DAY_START, "endTime": day_end,
                "brightness": ppfd, "fadeTime": LIGHT_FADE,
            }],
        },
    }


DEFAULT_PRESETS = {
    "sowing":     _stage((24, 24, 3), (80, 80, 5), (400, 400, 200), 80,  day_end=36000),
    "seedling":   _stage((24, 24, 3), (70, 70, 5), (600, 400, 200), 120, day_end=36000),
    "vegetative": _stage((24, 22, 3), (65, 65, 5), (800, 400, 200), 300, day_end=36000),
    "flowering":  _stage((24, 20, 3), (55, 55, 5), (800, 400, 200), 450, day_end=28800),
    "fruiting":   _stage((24, 20, 3), (50, 50, 5), (800, 400, 200), 550, day_end=22800),
}


def preset_names() -> list[str]:
    """Display names, in growth order."""
    return [name.capitalize() for name in DEFAULT_PRESETS]
