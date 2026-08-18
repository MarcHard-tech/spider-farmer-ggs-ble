"""Config flow for Spider Farmer GGS Controller."""
from __future__ import annotations

import re

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

from .const import CONF_MAC_ADDRESS, DOMAIN

MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


class SpiderFarmerGGSConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Spider Farmer GGS Controller."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered_mac: str | None = None

    # ── Auto-discovery (HA bluetooth scanner sees SF-GGS-CB) ─────────────────

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> config_entries.FlowResult:
        """Handle a device discovered via HA bluetooth scanning."""
        mac = discovery_info.address.upper()
        await self.async_set_unique_id(mac)
        self._abort_if_unique_id_configured()
        self._discovered_mac = mac
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        """Ask the user to confirm the auto-discovered device."""
        if user_input is not None:
            return self.async_create_entry(
                title=f"Spider Farmer GGS ({self._discovered_mac})",
                data={CONF_MAC_ADDRESS: self._discovered_mac},
            )
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"mac": self._discovered_mac},
        )

    # ── Manual setup ──────────────────────────────────────────────────────────

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        """Handle manual configuration by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            mac = user_input[CONF_MAC_ADDRESS].upper().strip()
            if not MAC_RE.match(mac):
                errors[CONF_MAC_ADDRESS] = "invalid_mac"
            else:
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Spider Farmer GGS ({mac})",
                    data={CONF_MAC_ADDRESS: mac},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    # No default: this must be the installer's own controller.
                    # It previously defaulted to the developer's device address,
                    # which both leaked that address and pre-filled a value that
                    # is wrong for everyone else. Find yours under
                    # Settings > Devices & Services > Bluetooth; it appears as
                    # "SF-GGS-CB".
                    vol.Required(CONF_MAC_ADDRESS): str,
                }
            ),
            errors=errors,
        )
