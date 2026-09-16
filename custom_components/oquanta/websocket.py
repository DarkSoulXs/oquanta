"""Websocket API and automation deploy for Oquanta flows."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.const import SERVICE_RELOAD, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .store import FlowStore, automation_id_for

_LOGGER = logging.getLogger(__name__)

AUTOMATION_DOMAIN = "automation"


@callback
def async_register(hass: HomeAssistant) -> None:
    """Register Oquanta websocket commands."""
    websocket_api.async_register_command(hass, ws_list)
    websocket_api.async_register_command(hass, ws_get)
    websocket_api.async_register_command(hass, ws_save_draft)
    websocket_api.async_register_command(hass, ws_save)
    websocket_api.async_register_command(hass, ws_set_enabled)
    websocket_api.async_register_command(hass, ws_delete)


def _store(hass: HomeAssistant) -> FlowStore:
    return hass.data[DOMAIN]["flow_store"]


def find_automation_entity(hass: HomeAssistant, automation_id: str) -> str | None:
    """Return entity_id whose attributes.id matches the automation unique id."""
    for state in hass.states.async_all(AUTOMATION_DOMAIN):
        if str(state.attributes.get("id", "")) == automation_id:
            return state.entity_id
    return None


def _summary(hass: HomeAssistant, record: dict[str, Any]) -> dict[str, Any]:
    graph = record.get("graph") if isinstance(record.get("graph"), dict) else {}
    meta = graph.get("meta") if isinstance(graph.get("meta"), dict) else {}
    automation_id = str(record.get("automation_id") or "")
    entity_id = find_automation_entity(hass, automation_id)
    enabled = meta.get("enabled", True)
    if entity_id:
        enabled = hass.states.is_state(entity_id, "on")
    return {
        "id": record.get("id"),
        "alias": meta.get("alias") or record.get("id"),
        "enabled": bool(enabled),
        "updated_at": record.get("updated_at"),
        "entity_id": entity_id,
        "automation_id": automation_id,
        "entity_ids": _entity_ids(graph),
        "deployed_at": record.get("deployed_at"),
        "unpublished": _unpublished(record),
    }


def _unpublished(record: dict[str, Any]) -> bool:
    deployed = record.get("deployed_at")
    updated = record.get("updated_at")
    if not deployed:
        return True
    if not isinstance(updated, str) or not isinstance(deployed, str):
        return False
    return updated > deployed


def _entity_ids(graph: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        return ids
    for node in nodes:
        if not isinstance(node, dict):
            continue
        data = node.get("data")
        if not isinstance(data, dict):
            continue
        for key in ("entityId", "waitEntityId"):
            value = data.get(key)
            if isinstance(value, str) and value:
                ids.append(value)
    return ids


@websocket_api.websocket_command({vol.Required("type"): "oquanta/list"})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_list(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    store = _store(hass)
    items = [_summary(hass, record) for record in store.flows.values()]
    items.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
    connection.send_result(msg["id"], items)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "oquanta/get",
        vol.Required("flow_id"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_get(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    record = _store(hass).flows.get(msg["flow_id"])
    if record is None:
        connection.send_error(msg["id"], "not_found", "Flow not found")
        return
    connection.send_result(msg["id"], record)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "oquanta/save_draft",
        vol.Required("graph"): dict,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_save_draft(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    graph = msg["graph"]
    meta = graph.get("meta") if isinstance(graph.get("meta"), dict) else {}
    flow_id = str(meta.get("id") or "")
    if not flow_id:
        connection.send_error(msg["id"], "invalid", "Flow is missing an id")
        return
    automation_id = automation_id_for(flow_id)
    record = await _store(hass).async_upsert(graph, automation_id)
    connection.send_result(
        msg["id"],
        {
            **_summary(hass, record),
            "graph": graph,
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "oquanta/save",
        vol.Required("graph"): dict,
        vol.Required("config"): dict,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_save(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    graph = msg["graph"]
    meta = graph.get("meta") if isinstance(graph.get("meta"), dict) else {}
    flow_id = str(meta.get("id") or "")
    if not flow_id:
        connection.send_error(msg["id"], "invalid", "Flow is missing an id")
        return
    automation_id = automation_id_for(flow_id)
    record = await _store(hass).async_upsert(graph, automation_id)
    deploy_error: str | None = None
    try:
        await hass.async_add_executor_job(
            _upsert_automation_yaml,
            _automations_path(hass),
            automation_id,
            _automation_payload(
                msg["config"],
                automation_id,
                bool(meta.get("enabled", True)),
            ),
        )
        await hass.services.async_call(
            AUTOMATION_DOMAIN, SERVICE_RELOAD, blocking=True
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Could not deploy Oquanta automation %s: %s", automation_id, err)
        deploy_error = str(err)
    else:
        marked = await _store(hass).async_mark_deployed(flow_id)
        if marked is not None:
            record = marked
    entity_id = find_automation_entity(hass, automation_id)
    connection.send_result(
        msg["id"],
        {
            **_summary(hass, record),
            "graph": graph,
            "entity_id": entity_id,
            "deploy_error": deploy_error,
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "oquanta/set_enabled",
        vol.Required("flow_id"): str,
        vol.Required("enabled"): bool,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_set_enabled(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    flow_id = str(msg["flow_id"])
    enabled = bool(msg["enabled"])
    store = _store(hass)
    record = await store.async_set_enabled(flow_id, enabled)
    if record is None:
        connection.send_error(msg["id"], "not_found", "Flow not found")
        return
    automation_id = str(record.get("automation_id") or automation_id_for(flow_id))
    try:
        if record.get("deployed_at"):
            await hass.async_add_executor_job(
                _patch_initial_state,
                _automations_path(hass),
                automation_id,
                enabled,
            )
        entity_id = find_automation_entity(hass, automation_id)
        if entity_id:
            await hass.services.async_call(
                AUTOMATION_DOMAIN,
                SERVICE_TURN_ON if enabled else SERVICE_TURN_OFF,
                {"entity_id": entity_id},
                blocking=True,
            )
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Could not set enabled for %s: %s", automation_id, err)
        connection.send_error(msg["id"], "ha_error", str(err))
        return
    connection.send_result(msg["id"], _summary(hass, record))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "oquanta/delete",
        vol.Required("flow_id"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_delete(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    flow_id = msg["flow_id"]
    record = _store(hass).flows.get(flow_id)
    if record is None:
        connection.send_error(msg["id"], "not_found", "Flow not found")
        return
    automation_id = str(record.get("automation_id") or automation_id_for(flow_id))
    try:
        await hass.async_add_executor_job(
            _remove_automation_yaml,
            _automations_path(hass),
            automation_id,
        )
        await hass.services.async_call(
            AUTOMATION_DOMAIN, SERVICE_RELOAD, blocking=True
        )
        registry = er.async_get(hass)
        leftover = find_automation_entity(hass, automation_id)
        if leftover:
            registry.async_remove(leftover)
        else:
            entity_id = registry.async_get_entity_id(
                AUTOMATION_DOMAIN, AUTOMATION_DOMAIN, automation_id
            )
            if entity_id:
                registry.async_remove(entity_id)
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Could not remove automation %s: %s", automation_id, err)
        connection.send_error(msg["id"], "ha_error", str(err))
        return
    await _store(hass).async_delete(flow_id)
    connection.send_result(msg["id"], {"id": flow_id})


def _automations_path(hass: HomeAssistant) -> str:
    try:
        from homeassistant.components.automation.config import (
            AUTOMATION_CONFIG_PATH,
        )
    except ImportError:
        AUTOMATION_CONFIG_PATH = "automations.yaml"
    return hass.config.path(AUTOMATION_CONFIG_PATH)


def _automation_payload(
    config: dict[str, Any], automation_id: str, enabled: bool
) -> dict[str, Any]:
    payload = dict(config)
    payload["id"] = automation_id
    payload["initial_state"] = enabled
    return payload


def _load_yaml_list(path: str) -> list[Any]:
    try:
        from homeassistant.util.yaml import load_yaml
    except ImportError:
        from homeassistant.util.yaml.loader import load_yaml

    if not Path(path).exists():
        return []
    data = load_yaml(path)
    if data is None:
        return []
    if not isinstance(data, list):
        raise ValueError("automations.yaml måste vara en lista")
    return data


def _save_yaml_list(path: str, data: list[Any]) -> None:
    try:
        from homeassistant.util.yaml import save_yaml
    except ImportError:
        from homeassistant.util.yaml.dumper import save_yaml

    save_yaml(path, data)


def _upsert_automation_yaml(
    path: str, automation_id: str, config: dict[str, Any]
) -> None:
    items = _load_yaml_list(path)
    updated = False
    for index, item in enumerate(items):
        if isinstance(item, dict) and str(item.get("id", "")) == automation_id:
            items[index] = config
            updated = True
            break
    if not updated:
        items.append(config)
    _save_yaml_list(path, items)


def _patch_initial_state(path: str, automation_id: str, enabled: bool) -> bool:
    items = _load_yaml_list(path)
    found = False
    for item in items:
        if isinstance(item, dict) and str(item.get("id", "")) == automation_id:
            item["initial_state"] = enabled
            found = True
            break
    if found:
        _save_yaml_list(path, items)
    return found


def _remove_automation_yaml(path: str, automation_id: str) -> None:
    items = _load_yaml_list(path)
    kept = [
        item
        for item in items
        if not (isinstance(item, dict) and str(item.get("id", "")) == automation_id)
    ]
    if len(kept) != len(items):
        _save_yaml_list(path, kept)
