"""Short sentences for the latest Oquanta run. No Home Assistant imports."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

STOPPED = "The latest run stopped."
STOPPED_SV = "Den senaste körningen stannade."
_WEEK = timedelta(days=7)


def logbook_message(execution: str, error: str, language: str = "en") -> str | None:
    """A line for an error or an aborted run. A finished run has none."""
    if execution not in {"error", "aborted"}:
        return None
    text = error.strip()
    if text:
        return text[:180]
    if language.lower().startswith("sv"):
        return STOPPED_SV
    return STOPPED


def runs_in_week(rows: list[dict[str, str]], now: datetime) -> int:
    """How many of these runs started within the last seven days."""
    moment = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
    cutoff = moment - _WEEK
    count = 0
    for row in rows:
        start = _parse_start(str(row.get("start") or ""))
        if start is None:
            continue
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if cutoff <= start <= moment:
            count += 1
    return count


def _parse_start(value: str) -> datetime | None:
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def claim_run(seen: set[str], run_id: str) -> bool:
    """True the first time this run id is seen."""
    if not run_id or run_id in seen:
        return False
    seen.add(run_id)
    return True
