"""Built-in planting stage presets.

Settings only — dates and stageId are supplied at deploy time. This tent is
a propagation tent used to raise vegetable seedlings for transplanting into
outdoor beds, not a grow-to-harvest tent, so there is no flowering or
fruiting stage. Temperature, humidity and PPFD values follow published
transplant-production DLI guidance (Purdue: DLI 10-15 for lettuce/cucumber/
squash/cabbage, 15-20 for tomato/pepper/eggplant; roughly 5-10 at
germination, 10-14 at cotyledon, 14-18 at true leaves, and 18-22 as plants
approach transplant size). They are starting points, not horticultural
gospel; the grower edits them from the dashboard.

No Home Assistant imports and no relative imports: this module is unit-tested
standalone.
"""
from __future__ import annotations

DAY_START = 64800   # 18:00 — lights on
DAY_END = 36000      # 10:00 — lights off (overnight light window, by design,
                     # to manage tent temperature)
LIGHT_FADE = 1800    # 30 min sunrise/sunset simulation
PPFD_MODE = 12


def _stage(temp, humi, co2, ppfd):
    """Build a preset body. temp/humi/co2 are (day, night, deadband).

    All presets share one light window (DAY_START-DAY_END). target.dayTime
    must match that window exactly: the dashboard derives its day/night
    climate switch from the light schedule, so "day" means "lamp on".
    """
    return {
        "target": {
            "dayTime": {"startTime": DAY_START, "endTime": DAY_END},
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
                "startTime": DAY_START, "endTime": DAY_END,
                "brightness": ppfd, "fadeTime": LIGHT_FADE,
            }],
        },
    }


DEFAULT_PRESETS = {
    # CO2 stays at 400 (ambient) throughout: the tent has no CO2 injection,
    # so a higher target would store a number nothing can act on.
    "germination":    _stage((22, 20, 2), (80, 80, 5), (400, 400, 200), 100),
    "seedling":       _stage((20, 18, 2), (70, 70, 5), (400, 400, 200), 210),
    "growing":        _stage((20, 17, 3), (60, 60, 5), (400, 400, 200), 280),
    "hardening off":  _stage((18, 15, 3), (55, 55, 5), (400, 400, 200), 350),
}


def preset_names() -> list[str]:
    """Display names, in growth order."""
    return [name.capitalize() for name in DEFAULT_PRESETS]
