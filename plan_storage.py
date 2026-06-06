"""Local storage for Spider Farmer GGS planting plans."""
from __future__ import annotations

import json
import logging
import os
from typing import Optional

from .const import PLAN_STORAGE_PATH

_LOGGER = logging.getLogger(__name__)


def _load_store() -> dict:
    """Load the plan storage file."""
    if not os.path.exists(PLAN_STORAGE_PATH):
        return {"plans": {}, "active_plan": None}
    try:
        with open(PLAN_STORAGE_PATH, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        _LOGGER.error("Failed to load plan storage: %s", exc)
        return {"plans": {}, "active_plan": None}


def _save_store(store: dict) -> None:
    """Save the plan storage file."""
    os.makedirs(os.path.dirname(PLAN_STORAGE_PATH), exist_ok=True)
    with open(PLAN_STORAGE_PATH, "w") as f:
        json.dump(store, f, indent=2)


def list_plans() -> dict[str, dict]:
    """Return all saved plans."""
    return _load_store().get("plans", {})


def get_plan(name: str) -> Optional[dict]:
    """Get a plan by name (case-insensitive key)."""
    store = _load_store()
    return store["plans"].get(name.lower())


def get_active_plan_name() -> Optional[str]:
    """Get the name of the currently active plan."""
    return _load_store().get("active_plan")


def save_plan(name: str, plan_data: dict) -> None:
    """Create or update a planting plan."""
    store = _load_store()
    key = name.lower()
    plan_data["name"] = name
    store["plans"][key] = plan_data
    _save_store(store)
    _LOGGER.info("Saved planting plan: %s", name)


def delete_plan(name: str) -> bool:
    """Delete a planting plan. Returns True if found and deleted."""
    store = _load_store()
    key = name.lower()
    if key in store["plans"]:
        del store["plans"][key]
        if store.get("active_plan") == key:
            store["active_plan"] = None
        _save_store(store)
        _LOGGER.info("Deleted planting plan: %s", name)
        return True
    return False


def set_active_plan(name: Optional[str]) -> None:
    """Set the active plan name (or None to deactivate)."""
    store = _load_store()
    store["active_plan"] = name.lower() if name else None
    _save_store(store)
