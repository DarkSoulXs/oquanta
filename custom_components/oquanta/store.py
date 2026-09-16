"""Persist Oquanta flow graphs."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import STORAGE_KEY, STORAGE_VERSION, AUTOMATION_ID_PREFIX


def automation_id_for(flow_id: str) -> str:
    """Return the Home Assistant automation unique id for a flow."""
    return f"{AUTOMATION_ID_PREFIX}{flow_id}"


class FlowStore:
    """Disk-backed map of Oquanta flows."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, STORAGE_KEY
        )
        self.flows: dict[str, dict[str, Any]] = {}

    async def async_load(self) -> None:
        loaded = await self._store.async_load()
        raw = loaded.get("flows") if isinstance(loaded, dict) else None
        if isinstance(raw, dict):
            self.flows = raw
        else:
            self.flows = {}

    async def async_save(self) -> None:
        await self._store.async_save({"flows": self.flows})

    async def async_upsert(
        self, graph: dict[str, Any], automation_id: str
    ) -> dict[str, Any]:
        meta = graph.get("meta") if isinstance(graph.get("meta"), dict) else {}
        flow_id = str(meta.get("id") or "")
        if not flow_id:
            raise ValueError("Flow is missing an id")
        existing = self.flows.get(flow_id) if isinstance(self.flows.get(flow_id), dict) else {}
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

    async def async_delete(self, flow_id: str) -> dict[str, Any] | None:
        record = self.flows.pop(flow_id, None)
        if record is not None:
            await self.async_save()
        return record
