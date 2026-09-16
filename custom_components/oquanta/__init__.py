"""Oquanta — visual flow editor for Home Assistant."""

from __future__ import annotations

import inspect
import logging
from pathlib import Path

import voluptuous as vol

from homeassistant.components import panel_custom
from homeassistant.components.update import UpdateEntity
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component, async_when_setup

from .const import (
    DOMAIN,
    GITHUB_REPO,
    PANEL_URL_PATH,
    PANEL_WEBCOMPONENT,
    STATIC_URL_PATH,
    integration_version,
)
from .store import FlowStore
from .update import OquantaUpdateCoordinator, OquantaUpdateEntity
from .websocket import async_register as async_register_websocket

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(DOMAIN): vol.Any(
            None,
            vol.Schema(
                {vol.Optional("github_repo"): cv.string},
                extra=vol.ALLOW_EXTRA,
            ),
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Oquanta panel, static files and update checks."""
    domain_config = config.get(DOMAIN) or {}
    github_repo = GITHUB_REPO
    if isinstance(domain_config, dict):
        repo = domain_config.get("github_repo")
        if isinstance(repo, str) and repo.strip():
            github_repo = repo.strip()

    coordinator = OquantaUpdateCoordinator(hass, github_repo)
    flow_store = FlowStore(hass)
    hass.data[DOMAIN] = {
        "coordinator": coordinator,
        "flow_store": flow_store,
        "github_repo": github_repo,
        "version": integration_version(),
        "pending_restart": False,
        "install_error": False,
    }
    await flow_store.async_load()
    async_register_websocket(hass)

    await _async_register_static_paths(hass)
    await async_setup_component(hass, "panel_custom", config)
    await _async_register_panel(hass)
    await async_setup_component(hass, "update", config)

    async def _add_update_entity(hass: HomeAssistant, _component: str) -> None:
        if hass.data[DOMAIN].get("update_registered"):
            return
        hass.data[DOMAIN]["update_registered"] = True
        entity_component: EntityComponent[UpdateEntity] = hass.data["update"]
        added = entity_component.async_add_entities(
            [OquantaUpdateEntity(hass, coordinator)]
        )
        if inspect.isawaitable(added):
            await added

    async_when_setup(hass, "update", _add_update_entity)

    async def _refresh_on_start(_event: object) -> None:
        await coordinator.async_refresh()

    if hass.is_running:
        hass.async_create_task(coordinator.async_refresh())
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _refresh_on_start)

    return True


async def _async_register_static_paths(hass: HomeAssistant) -> None:
    www_path = Path(__file__).parent / "www"
    www_path.mkdir(parents=True, exist_ok=True)
    try:
        from homeassistant.components.http import StaticPathConfig

        await hass.http.async_register_static_paths(
            [StaticPathConfig(STATIC_URL_PATH, str(www_path), False)]
        )
    except (ImportError, AttributeError):
        hass.http.register_static_path(STATIC_URL_PATH, str(www_path), False)


async def _async_register_panel(hass: HomeAssistant) -> None:
    version = integration_version()
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name=PANEL_WEBCOMPONENT,
        sidebar_title="Oquanta",
        sidebar_icon="mdi:hexagon-outline",
        module_url=f"{STATIC_URL_PATH}/oquanta-panel.js?v={version}",
        embed_iframe=True,
        require_admin=True,
    )
    _LOGGER.debug("Oquanta panel registered (version %s)", version)
