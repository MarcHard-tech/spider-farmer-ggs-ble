"""Storage for planting stage presets.

Presets are stage bodies without dates or stageId. The controller holds what is
actually running; this file only holds what is available to deploy.

No relative imports: this module is unit-tested standalone.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Optional

# Inside Home Assistant this module is part of a package, so the import must be
# relative. Standalone under pytest-less `python3` it is not, so fall back.
# Without both, either the integration or the tests break.
try:
    from . import presets as _presets
except ImportError:
    import presets as _presets

_LOGGER = logging.getLogger(__name__)

DEFAULT_PATH = "/config/spider_farmer_ggs/presets.json"


def _load(path: str) -> dict:
    if not os.path.exists(path):
        return {"presets": {}}
    try:
        with open(path, encoding="utf-8") as handle:
            store = json.load(handle)
    except (json.JSONDecodeError, OSError) as exc:
        _LOGGER.error("Failed to load preset store %s: %s", path, exc)
        return {"presets": {}}
    if not isinstance(store, dict):
        _LOGGER.error("Preset store %s did not contain a JSON object", path)
        return {"presets": {}}
    store.setdefault("presets", {})
    return store


def _save(path: str, store: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(store, handle, indent=2)


def seed_defaults(path: str = DEFAULT_PATH) -> None:
    """Add any built-in presets the store does not already have.

    Never overwrites an existing entry — the grower's edits win.
    """
    store = _load(path)
    changed = False
    for name, body in _presets.DEFAULT_PRESETS.items():
        key = name.lower()
        if key not in store["presets"]:
            store["presets"][key] = json.loads(json.dumps(body))
            changed = True
    if changed:
        _save(path, store)


def list_presets(path: str = DEFAULT_PATH) -> list[str]:
    return list(_load(path)["presets"])


def list_all(path: str = DEFAULT_PATH) -> dict:
    """Return the full {name: body} mapping from a single consistent read.

    Unlike calling list_presets() then get_preset() once per name, this loads
    the store exactly once, so a concurrent save/delete between separate reads
    can't leave a stale name pointing at a now-missing preset (which would show
    up as a None value in the result).
    """
    return dict(_load(path)["presets"])


def get_preset(path: str = DEFAULT_PATH, name: str = "") -> Optional[dict]:
    return _load(path)["presets"].get(name.lower())


def save_preset(path: str, name: str, body: dict) -> None:
    store = _load(path)
    store["presets"][name.lower()] = body
    _save(path, store)


def delete_preset(path: str, name: str) -> None:
    store = _load(path)
    store["presets"].pop(name.lower(), None)
    _save(path, store)
