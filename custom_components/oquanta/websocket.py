"""Websocket API and automation deploy for Oquanta flows."""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import voluptuous as vol
import yaml

from homeassistant.components import websocket_api
from homeassistant.const import SERVICE_RELOAD, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .store import FlowStore, automation_id_for, script_id_for
from .yaml_util import parse_yaml_mapping

_LOGGER = logging.getLogger(__name__)

AUTOMATION_DOMAIN = "automation"
SCRIPT_DOMAIN = "script"


@callback
def async_register(hass: HomeAssistant) -> None:
    """Register Oquanta websocket commands."""
    websocket_api.async_register_command(hass, ws_list)
    websocket_api.async_register_command(hass, ws_list_trash)
    websocket_api.async_register_command(hass, ws_get)
    websocket_api.async_register_command(hass, ws_save_draft)
    websocket_api.async_register_command(hass, ws_save)
    websocket_api.async_register_command(hass, ws_set_enabled)
    websocket_api.async_register_command(hass, ws_delete)
    websocket_api.async_register_command(hass, ws_restore)
    websocket_api.async_register_command(hass, ws_empty_trash)
    websocket_api.async_register_command(hass, ws_purge_trash)
    websocket_api.async_register_command(hass, ws_export)
    websocket_api.async_register_command(hass, ws_import)
    websocket_api.async_register_command(hass, ws_revisions)
    websocket_api.async_register_command(hass, ws_restore_revision)
    websocket_api.async_register_command(hass, ws_parse_yaml)


def _store(hass: HomeAssistant) -> FlowStore:
    return hass.data[DOMAIN]["flow_store"]


def find_automation_entity(hass: HomeAssistant, automation_id: str) -> str | None:
    """Return entity_id whose attributes.id matches the automation unique id."""
    for state in hass.states.async_all(AUTOMATION_DOMAIN):
        if str(state.attributes.get("id", "")) == automation_id:
            return state.entity_id
    return None


def find_script_entity(hass: HomeAssistant, script_id: str) -> str | None:
    """Return script entity_id if it exists."""
    entity_id = f"{SCRIPT_DOMAIN}.{script_id}"
    if hass.states.get(entity_id) is not None:
        return entity_id
    return None


def _flow_kind(meta: dict[str, Any]) -> str:
    kind = str(meta.get("kind") or "automation")
    return "script" if kind == "script" else "automation"


def _summary(hass: HomeAssistant, record: dict[str, Any]) -> dict[str, Any]:
    graph = record.get("graph") if isinstance(record.get("graph"), dict) else {}
    meta = graph.get("meta") if isinstance(graph.get("meta"), dict) else {}
    kind = _flow_kind(meta)
    automation_id = str(record.get("automation_id") or "")
    script_id = script_id_for(str(record.get("id") or meta.get("id") or ""))
    entity_id = (
        find_script_entity(hass, script_id)
        if kind == "script"
        else find_automation_entity(hass, automation_id)
    )
    enabled = meta.get("enabled", True)
    if entity_id and kind != "script":
        enabled = hass.states.is_state(entity_id, "on")
    payload = {
        "id": record.get("id"),
        "alias": meta.get("alias") or record.get("id"),
        "kind": kind,
        "enabled": bool(enabled),
        "updated_at": record.get("updated_at"),
        "entity_id": entity_id,
        "automation_id": automation_id,
        "entity_ids": _entity_ids(graph),
        "deployed_at": record.get("deployed_at"),
        "unpublished": _unpublished(record),
        "folder": str(meta.get("folder") or ""),
        "tags": _meta_tags(meta),
        "pinned": bool(meta.get("pinned")),
        "node_count": _node_count(graph),
        "description": str(meta.get("description") or ""),
        "fields": _meta_fields(meta),
    }
    if record.get("deleted_at"):
        payload["deleted_at"] = record.get("deleted_at")
    return payload


def _meta_fields(meta: dict[str, Any]) -> list[dict[str, str]]:
    raw = meta.get("fields")
    if not isinstance(raw, list):
        return []
    fields: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        if not key:
            continue
        fields.append({"key": key, "value": str(item.get("value") or "")})
    return fields


def _meta_tags(meta: dict[str, Any]) -> list[str]:
    raw = meta.get("tags")
    if not isinstance(raw, list):
        return []
    tags: list[str] = []
    for item in raw:
        text = str(item).strip()
        if text and text not in tags:
            tags.append(text)
    return tags


def _node_count(graph: dict[str, Any]) -> int:
    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        return 0
    return len(nodes)


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
    store = _store(hass)
    previous = store.flows.get(flow_id)
    if isinstance(previous, dict):
        prev_graph = previous.get("graph")
        if isinstance(prev_graph, dict):
            await store.async_add_revision(flow_id, prev_graph)
    record = await store.async_upsert(graph, automation_id)
    deploy_error: str | None = None
    kind = _flow_kind(meta)
    try:
        if kind == "script":
            script_id = script_id_for(flow_id)
            await hass.async_add_executor_job(
                _upsert_script_yaml,
                _scripts_path(hass),
                script_id,
                dict(msg["config"]),
            )
            await hass.services.async_call(SCRIPT_DOMAIN, SERVICE_RELOAD, blocking=True)
        else:
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
        _LOGGER.warning("Could not deploy Oquanta %s %s: %s", kind, automation_id, err)
        deploy_error = str(err)
    else:
        marked = await store.async_mark_deployed(flow_id)
        if marked is not None:
            record = marked
    connection.send_result(
        msg["id"],
        {
            **_summary(hass, record),
            "graph": graph,
            "entity_id": _summary(hass, record).get("entity_id"),
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
    graph = record.get("graph") if isinstance(record.get("graph"), dict) else {}
    meta = graph.get("meta") if isinstance(graph.get("meta"), dict) else {}
    kind = _flow_kind(meta)
    try:
        if kind == "script":
            connection.send_result(msg["id"], _summary(hass, record))
            return
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


@websocket_api.websocket_command({vol.Required("type"): "oquanta/list_trash"})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_list_trash(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    store = _store(hass)
    items = [_summary(hass, record) for record in store.trash.values()]
    items.sort(key=lambda item: str(item.get("deleted_at") or ""), reverse=True)
    connection.send_result(msg["id"], items)


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
    flow_id = str(msg["flow_id"])
    record = _store(hass).flows.get(flow_id)
    if record is None:
        connection.send_error(msg["id"], "not_found", "Flow not found")
        return
    error = await _undeploy_record(hass, record)
    if error is not None:
        connection.send_error(msg["id"], "ha_error", error)
        return
    trashed = await _store(hass).async_soft_delete(flow_id)
    connection.send_result(msg["id"], {"id": flow_id, "deleted_at": (trashed or {}).get("deleted_at")})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "oquanta/restore",
        vol.Required("flow_id"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_restore(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    record = await _store(hass).async_restore(str(msg["flow_id"]))
    if record is None:
        connection.send_error(msg["id"], "not_found", "Flow not found")
        return
    connection.send_result(msg["id"], _summary(hass, record))


@websocket_api.websocket_command({vol.Required("type"): "oquanta/empty_trash"})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_empty_trash(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    count = await _store(hass).async_empty_trash()
    connection.send_result(msg["id"], {"removed": count})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "oquanta/purge_trash",
        vol.Required("flow_id"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_purge_trash(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    record = await _store(hass).async_purge_trash_item(str(msg["flow_id"]))
    if record is None:
        connection.send_error(msg["id"], "not_found", "Flow not found")
        return
    connection.send_result(msg["id"], {"id": msg["flow_id"]})


@websocket_api.websocket_command({vol.Required("type"): "oquanta/export"})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_export(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    store = _store(hass)
    flows: list[dict[str, Any]] = []
    for record in store.flows.values():
        if not isinstance(record, dict):
            continue
        graph = record.get("graph")
        if not isinstance(graph, dict):
            continue
        flows.append(
            {
                "graph": graph,
                "updated_at": record.get("updated_at"),
                "deployed_at": record.get("deployed_at"),
            }
        )
    connection.send_result(
        msg["id"],
        {"version": 1, "flows": flows},
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "oquanta/import",
        vol.Required("flows"): list,
        vol.Optional("replace", default=False): bool,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_import(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    store = _store(hass)
    replace = bool(msg.get("replace"))
    imported = 0
    skipped = 0
    for item in msg["flows"]:
        graph = item.get("graph") if isinstance(item, dict) else item
        if not isinstance(graph, dict):
            skipped += 1
            continue
        meta = graph.get("meta") if isinstance(graph.get("meta"), dict) else {}
        flow_id = str(meta.get("id") or "")
        if not flow_id:
            skipped += 1
            continue
        if flow_id in store.flows and not replace:
            skipped += 1
            continue
        await store.async_upsert(graph, automation_id_for(flow_id))
        imported += 1
    connection.send_result(msg["id"], {"imported": imported, "skipped": skipped})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "oquanta/revisions",
        vol.Required("flow_id"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_revisions(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    rows = _store(hass).list_revisions(str(msg["flow_id"]))
    connection.send_result(msg["id"], rows)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "oquanta/restore_revision",
        vol.Required("flow_id"): str,
        vol.Required("saved_at"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_restore_revision(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    record = await _store(hass).async_restore_revision(
        str(msg["flow_id"]), str(msg["saved_at"])
    )
    if record is None:
        connection.send_error(msg["id"], "not_found", "Revision not found")
        return
    connection.send_result(msg["id"], _summary(hass, record))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "oquanta/parse_yaml",
        vol.Required("yaml"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_parse_yaml(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    try:
        parsed = parse_yaml_mapping(str(msg["yaml"]))
    except yaml.YAMLError as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    connection.send_result(msg["id"], parsed)
    _ = hass


async def _undeploy_record(hass: HomeAssistant, record: dict[str, Any]) -> str | None:
    flow_id = str(record.get("id") or "")
    automation_id = str(record.get("automation_id") or automation_id_for(flow_id))
    graph = record.get("graph") if isinstance(record.get("graph"), dict) else {}
    meta = graph.get("meta") if isinstance(graph.get("meta"), dict) else {}
    kind = _flow_kind(meta)
    script_id = script_id_for(flow_id)
    try:
        if kind == "script":
            await hass.async_add_executor_job(
                _remove_script_yaml,
                _scripts_path(hass),
                script_id,
            )
            await hass.services.async_call(SCRIPT_DOMAIN, SERVICE_RELOAD, blocking=True)
            registry = er.async_get(hass)
            leftover = find_script_entity(hass, script_id)
            if leftover:
                registry.async_remove(leftover)
            else:
                entity_id = registry.async_get_entity_id(
                    SCRIPT_DOMAIN, SCRIPT_DOMAIN, script_id
                )
                if entity_id:
                    registry.async_remove(entity_id)
        else:
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
        _LOGGER.warning("Could not remove %s %s: %s", kind, automation_id, err)
        return str(err)
    return None


def _scripts_path(hass: HomeAssistant) -> str:
    try:
        from homeassistant.components.script import SCRIPT_CONFIG_PATH
    except ImportError:
        SCRIPT_CONFIG_PATH = "scripts.yaml"
    return hass.config.path(SCRIPT_CONFIG_PATH)


def _load_yaml(path: str) -> Any:
    try:
        from homeassistant.util.yaml import load_yaml
    except ImportError:
        from homeassistant.util.yaml.loader import load_yaml

    if not Path(path).exists():
        return None
    return load_yaml(path)


def _backup_yaml(path: str) -> None:
    src = Path(path)
    if not src.is_file():
        return
    shutil.copy2(src, src.with_name(f"{src.name}.oquanta.bak"))


def _atomic_save_yaml(path: str, data: Any) -> None:
    try:
        from homeassistant.util.yaml import save_yaml
    except ImportError:
        from homeassistant.util.yaml.dumper import save_yaml

    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp_name = tempfile.mkstemp(
        prefix=f".{dest.name}.",
        suffix=".tmp",
        dir=dest.parent,
    )
    os.close(handle)
    tmp_path = Path(tmp_name)
    try:
        _backup_yaml(str(dest))
        save_yaml(str(tmp_path), data)
        os.replace(tmp_path, dest)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def _load_yaml_mapping(path: str) -> dict[str, Any]:
    data = _load_yaml(path)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError("scripts.yaml must be a mapping, not a list")
    return data


def _save_yaml_mapping(path: str, data: dict[str, Any]) -> None:
    _atomic_save_yaml(path, data)


def _upsert_script_yaml(path: str, script_id: str, config: dict[str, Any]) -> None:
    items = _load_yaml_mapping(path)
    items[script_id] = config
    _save_yaml_mapping(path, items)


def _remove_script_yaml(path: str, script_id: str) -> None:
    items = _load_yaml_mapping(path)
    if script_id in items:
        del items[script_id]
        _save_yaml_mapping(path, items)


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
    data = _load_yaml(path)
    if data is None:
        return []
    if not isinstance(data, list):
        raise ValueError("automations.yaml must be a list")
    return data


def _save_yaml_list(path: str, data: list[Any]) -> None:
    _atomic_save_yaml(path, data)


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
