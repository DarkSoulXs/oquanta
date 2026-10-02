"""Whether a published script should be heard by Assist. No Home Assistant imports."""

from __future__ import annotations

ASSISTANT = "conversation"


def assist_exposure(kind: str, phrase: str) -> tuple[bool, str] | None:
    """None unless this is a script. Otherwise whether to expose it, and the name Assist hears."""
    if kind != "script":
        return None
    heard = phrase.strip()
    return bool(heard), heard
