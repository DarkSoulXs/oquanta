"""Config flow for Oquanta."""

from __future__ import annotations

from homeassistant.config_entries import ConfigFlow
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN


class OquantaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Single-instance config flow. No options; github_repo stays in const."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, object] | None = None
    ) -> FlowResult:
        """Create one empty config entry from the UI."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(title="Oquanta", data={})
        return self.async_show_form(step_id="user")

    async def async_step_import(
        self, user_input: dict[str, object] | None = None
    ) -> FlowResult:
        """Migrate yaml `oquanta:` to a config entry without duplicates."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="Oquanta", data={})
