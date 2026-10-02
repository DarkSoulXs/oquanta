"""Repair when the latest Oquanta run failed, and clear it after a later success."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_track_time_interval

from .const import AUTOMATION_ID_PREFIX, DOMAIN
from .trace_note import claim_run, logbook_message, runs_in_week

_LOGGER = logging.getLogger(__name__)
_ISSUE_PREFIX = "trace_failed_"
_INTERVAL = timedelta(minutes=15)


def async_start_trace_watch(hass: HomeAssistant) -> None:
    """Check traces once Home Assistant is up, then about every fifteen minutes."""

    async def _begin(_event: object | None = None) -> None:
        if DOMAIN not in hass.data or hass.data[DOMAIN].get("trace_unsub"):
            return
        _sync_issues(hass)
        hass.data[DOMAIN]["trace_unsub"] = async_track_time_interval(
            hass, _tick, _INTERVAL
        )

    def _tick(_now: datetime) -> None:
        _sync_issues(hass)

    if hass.is_running:
        hass.async_create_task(_begin())
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _begin)


def async_stop_trace_watch(hass: HomeAssistant) -> None:
    """Stop the interval when the integration unloads."""
    data = hass.data.get(DOMAIN)
    if not isinstance(data, dict):
        return
    unsub = data.pop("trace_unsub", None)
    if callable(unsub):
        unsub()


def latest_run_failed(rows: list[dict[str, str]]) -> bool:
    """True only when the newest run ended with an error."""
    if not rows:
        return False
    ordered = sorted(rows, key=lambda row: row.get("start") or "")
    return ordered[-1].get("execution") == "error"


def _sync_issues(hass: HomeAssistant) -> None:
    if DOMAIN not in hass.data:
        return
    try:
        current: set[str] = set()
        sentences: dict[str, str] = hass.data[DOMAIN].setdefault("sentences", {})
        counts: dict[str, int] = hass.data[DOMAIN].setdefault("runs_week", {})
        logged: set[str] = hass.data[DOMAIN].setdefault("logged_runs", set())
        now = datetime.now(timezone.utc)
        for domain, item_id, alias, entity_id in _oquanta_items(hass):
            current.add(item_id)
            rows = _trace_rows(hass, domain, item_id)
            row = _latest_row(rows)
            failed = bool(row) and row.get("execution") == "error"
            _set_issue(hass, item_id, alias, failed)
            _remember_sentence(hass, sentences, logged, item_id, alias, entity_id, row)
            counts[item_id] = runs_in_week(rows, now)
        for item_id in list(counts):
            if item_id not in current:
                counts.pop(item_id, None)
        _drop_missing(hass, current)
    except Exception:  # noqa: BLE001 — trace storage differs between HA versions
        _LOGGER.debug("Oquanta could not read automation traces", exc_info=True)


def runs_this_week(hass: HomeAssistant, item_id: str) -> int:
    """Runs stored for one Oquanta automation or script during the last seven days."""
    data = hass.data.get(DOMAIN)
    if not isinstance(data, dict):
        return 0
    counts = data.get("runs_week")
    if not isinstance(counts, dict):
        return 0
    value = counts.get(item_id)
    return value if isinstance(value, int) else 0


def last_sentence(hass: HomeAssistant, item_id: str) -> str:
    """The short sentence stored for one Oquanta automation or script."""
    data = hass.data.get(DOMAIN)
    if not isinstance(data, dict):
        return ""
    sentences = data.get("sentences")
    if not isinstance(sentences, dict):
        return ""
    value = sentences.get(item_id)
    return value if isinstance(value, str) else ""


def _oquanta_items(hass: HomeAssistant) -> list[tuple[str, str, str, str]]:
    items: list[tuple[str, str, str, str]] = []
    for state in hass.states.async_all():
        entity_id = state.entity_id
        if entity_id.startswith("automation."):
            item_id = state.attributes.get("id")
            if isinstance(item_id, str) and item_id.startswith(AUTOMATION_ID_PREFIX):
                items.append(("automation", item_id, state.name or item_id, entity_id))
        elif entity_id.startswith("script."):
            object_id = entity_id.split(".", 1)[1]
            if object_id.startswith(AUTOMATION_ID_PREFIX):
                items.append(("script", object_id, state.name or object_id, entity_id))
    return items


def _trace_rows(hass: HomeAssistant, domain: str, item_id: str) -> list[dict[str, str]]:
    bucket = _trace_map(hass).get((domain, item_id))
    if bucket is None:
        return []
    values = list(bucket.values()) if isinstance(bucket, dict) else list(bucket)
    rows: list[dict[str, str]] = []
    for trace in values:
        row = _trace_row(trace)
        if row:
            rows.append(row)
    return rows


def _trace_map(hass: HomeAssistant) -> dict[Any, Any]:
    data = hass.data.get("trace")
    if not isinstance(data, dict):
        return {}
    if any(isinstance(key, tuple) for key in data):
        return data
    nested = data.get("traces")
    if isinstance(nested, dict):
        return nested
    return {}


def _trace_row(trace: object) -> dict[str, str] | None:
    short: dict[str, Any] = {}
    if hasattr(trace, "as_short_dict"):
        try:
            raw = trace.as_short_dict()
        except Exception:  # noqa: BLE001 — a broken trace should not stop the scan
            raw = None
        if isinstance(raw, dict):
            short = raw
    timestamp = short.get("timestamp")
    start = ""
    if isinstance(timestamp, dict) and isinstance(timestamp.get("start"), str):
        start = timestamp["start"]
    elif isinstance(getattr(trace, "_timestamp_start", None), str):
        start = trace._timestamp_start  # noqa: SLF001 — HA stores the start privately
    execution = short.get("script_execution")
    if not isinstance(execution, str):
        execution = getattr(trace, "_script_execution", "")
    if not isinstance(execution, str):
        return None
    run_id = short.get("run_id")
    if not isinstance(run_id, str):
        run_id = str(getattr(trace, "run_id", "") or "")
    error = short.get("error")
    if not isinstance(error, str):
        raw_error = getattr(trace, "error", None)
        error = str(raw_error) if raw_error else ""
    return {"start": start, "execution": execution, "run_id": run_id, "error": error}


def _latest_row(rows: list[dict[str, str]]) -> dict[str, str] | None:
    if not rows:
        return None
    return sorted(rows, key=lambda row: row.get("start") or "")[-1]


def _remember_sentence(
    hass: HomeAssistant,
    sentences: dict[str, str],
    logged: set[str],
    item_id: str,
    alias: str,
    entity_id: str,
    row: dict[str, str] | None,
) -> None:
    if row is None:
        sentences.pop(item_id, None)
        return
    language = str(getattr(getattr(hass, "config", None), "language", "") or "")
    message = logbook_message(row.get("execution") or "", row.get("error") or "", language)
    if not message:
        sentences.pop(item_id, None)
        return
    sentences[item_id] = message
    run_id = row.get("run_id") or row.get("start") or ""
    if claim_run(logged, run_id):
        _write_logbook(hass, alias, message, entity_id)


def _write_logbook(
    hass: HomeAssistant, name: str, message: str, entity_id: str
) -> None:
    try:
        from homeassistant.components.logbook import async_log_entry

        async_log_entry(hass, name, message, DOMAIN, entity_id)
    except Exception:  # noqa: BLE001 — logbook is optional across HA versions
        _LOGGER.debug("Oquanta could not write a logbook line", exc_info=True)


def _set_issue(hass: HomeAssistant, item_id: str, alias: str, failed: bool) -> None:
    issue_id = f"{_ISSUE_PREFIX}{item_id}"
    registry = ir.async_get(hass)
    exists = (DOMAIN, issue_id) in registry.issues
    if failed and not exists:
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="trace_failed",
            translation_placeholders={"name": alias},
        )
        return
    if not failed and exists:
        ir.async_delete_issue(hass, DOMAIN, issue_id)


def _drop_missing(hass: HomeAssistant, current: set[str]) -> None:
    registry = ir.async_get(hass)
    for issue in list(registry.issues.values()):
        if issue.domain != DOMAIN or not str(issue.issue_id).startswith(_ISSUE_PREFIX):
            continue
        item_id = str(issue.issue_id)[len(_ISSUE_PREFIX) :]
        if item_id not in current:
            ir.async_delete_issue(hass, DOMAIN, issue.issue_id)
