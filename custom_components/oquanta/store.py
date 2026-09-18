"""Persist Oquanta flow graphs."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import STORAGE_KEY, STORAGE_VERSION, AUTOMATION_ID_PREFIX

REVISION_LIMIT = 10


def automation_id_for(flow_id: str) -> str:
    """Return the Home Assistant automation unique id for a flow."""
    return f"{AUTOMATION_ID_PREFIX}{flow_id}"


def script_id_for(flow_id: str) -> str:
    """Return the Home Assistant script object id for a flow."""
    return f"{AUTOMATION_ID_PREFIX}{flow_id.replace('-', '_')}"


def _as_map(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _draft_updated_at(deployed_at: Any) -> str:
    now = dt_util.utcnow()
    if isinstance(deployed_at, str) and deployed_at:
        parsed = dt_util.parse_datetime(deployed_at)
        if parsed is not None and now <= parsed:
            now = parsed + timedelta(milliseconds=1)
    return now.isoformat()


class FlowStore:
    """Disk-backed map of Oquanta flows."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, STORAGE_KEY
        )
        self.flows: dict[str, dict[str, Any]] = {}
        self.trash: dict[str, dict[str, Any]] = {}
        self.revisions: dict[str, list[dict[str, Any]]] = {}

    async def async_load(self) -> None:
        loaded = await self._store.async_load()
        data = loaded if isinstance(loaded, dict) else {}
        flows = data.get("flows")
        self.flows = flows if isinstance(flows, dict) else {}
        trash = data.get("trash")
        self.trash = trash if isinstance(trash, dict) else {}
        revisions = data.get("revisions")
        self.revisions = revisions if isinstance(revisions, dict) else {}

    async def async_save(self) -> None:
        await self._store.async_save(
            {
                "flows": self.flows,
                "trash": self.trash,
                "revisions": self.revisions,
            }
        )

    async def async_upsert(
        self, graph: dict[str, Any], automation_id: str
    ) -> dict[str, Any]:
        meta = _as_map(graph.get("meta"))
        flow_id = str(meta.get("id") or "")
        if not flow_id:
            raise ValueError("Flow is missing an id")
        existing = _as_map(self.flows.get(flow_id))
        record = {
            "id": flow_id,
            "graph": graph,
            "automation_id": automation_id,
            "updated_at": dt_util.utcnow().isoformat(),
            "deployed_at": existing.get("deployed_at") if existing else None,
        }
        self.flows[flow_id] = record
        await self.async_save()
        return record

    async def async_mark_deployed(self, flow_id: str) -> dict[str, Any] | None:
        record = self.flows.get(flow_id)
        if not isinstance(record, dict):
            return None
        record["deployed_at"] = record.get("updated_at") or dt_util.utcnow().isoformat()
        self.flows[flow_id] = record
        await self.async_save()
        return record

    async def async_set_enabled(
        self, flow_id: str, enabled: bool
    ) -> dict[str, Any] | None:
        record = self.flows.get(flow_id)
        if not isinstance(record, dict):
            return None
        graph = _as_map(record.get("graph"))
        meta = _as_map(graph.get("meta"))
        graph = {**graph, "meta": {**meta, "enabled": enabled}}
        record = {**record, "graph": graph}
        self.flows[flow_id] = record
        await self.async_save()
        return record

    async def async_delete(self, flow_id: str) -> dict[str, Any] | None:
        """Permanently remove a live flow (legacy). Prefer async_soft_delete."""
        record = self.flows.pop(flow_id, None)
        if record is not None:
            await self.async_save()
        return record

    async def async_soft_delete(self, flow_id: str) -> dict[str, Any] | None:
        record = self.flows.pop(flow_id, None)
        if not isinstance(record, dict):
            return None
        trashed = {
            **record,
            "deleted_at": dt_util.utcnow().isoformat(),
        }
        self.trash[flow_id] = trashed
        await self.async_save()
        return trashed

    async def async_restore(self, flow_id: str) -> dict[str, Any] | None:
        record = self.trash.pop(flow_id, None)
        if not isinstance(record, dict):
            return None
        if flow_id in self.flows:
            self.trash[flow_id] = record
            return None
        restored = {
            **record,
            "updated_at": _draft_updated_at(record.get("deployed_at")),
        }
        restored.pop("deleted_at", None)
        self.flows[flow_id] = restored
        await self.async_save()
        return restored

    async def async_empty_trash(self) -> int:
        count = len(self.trash)
        for flow_id in list(self.trash):
            self.revisions.pop(flow_id, None)
        self.trash = {}
        await self.async_save()
        return count

    async def async_purge_trash_item(self, flow_id: str) -> dict[str, Any] | None:
        record = self.trash.pop(flow_id, None)
        if record is not None:
            self.revisions.pop(flow_id, None)
            await self.async_save()
        return record

    async def async_add_revision(
        self, flow_id: str, graph: dict[str, Any]
    ) -> None:
        if not flow_id or not isinstance(graph, dict):
            return
        entry = {
            "saved_at": dt_util.utcnow().isoformat(),
            "graph": graph,
        }
        history = self.revisions.get(flow_id)
        if not isinstance(history, list):
            history = []
        history = [*history, entry][-REVISION_LIMIT:]
        self.revisions[flow_id] = history
        await self.async_save()

    def list_revisions(self, flow_id: str) -> list[dict[str, Any]]:
        history = self.revisions.get(flow_id)
        if not isinstance(history, list):
            return []
        rows: list[dict[str, Any]] = []
        for item in reversed(history):
            if not isinstance(item, dict):
                continue
            graph = _as_map(item.get("graph"))
            meta = _as_map(graph.get("meta"))
            rows.append(
                {
                    "saved_at": item.get("saved_at"),
                    "alias": meta.get("alias") or flow_id,
                    "nodes": [
                        {
                            "id": str(node.get("id") or ""),
                            "kind": str((_as_map(node.get("data")).get("kind") or "")),
                            "label": str(
                                (_as_map(node.get("data")).get("notes") or "")
                                or (_as_map(node.get("data")).get("kind") or "")
                            ),
                        }
                        for node in graph.get("nodes") or []
                        if isinstance(node, dict)
                    ],
                }
            )
        return rows

    async def async_restore_revision(
        self, flow_id: str, saved_at: str
    ) -> dict[str, Any] | None:
        history = self.revisions.get(flow_id)
        if not isinstance(history, list):
            return None
        match: dict[str, Any] | None = None
        for item in history:
            if isinstance(item, dict) and str(item.get("saved_at") or "") == saved_at:
                match = item
                break
        if match is None:
            return None
        graph = _as_map(match.get("graph"))
        if not graph:
            return None
        existing = _as_map(self.flows.get(flow_id))
        automation_id = str(
            existing.get("automation_id") or automation_id_for(flow_id)
        )
        record = await self.async_upsert(graph, automation_id)
        record = {
            **record,
            "updated_at": _draft_updated_at(record.get("deployed_at")),
        }
        self.flows[flow_id] = record
        await self.async_save()
        return record
