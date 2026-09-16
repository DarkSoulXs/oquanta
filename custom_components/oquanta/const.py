"""Constants for Oquanta."""

from __future__ import annotations

import json
from pathlib import Path

DOMAIN = "oquanta"
PANEL_URL_PATH = "oquanta"
PANEL_WEBCOMPONENT = "oquanta-panel"
STATIC_URL_PATH = "/oquanta-files"
GITHUB_REPO = "DarkSoulXs/oquanta"
UPDATE_SCAN_HOURS = 12
STORAGE_KEY = "oquanta_flows"
STORAGE_VERSION = 1
AUTOMATION_ID_PREFIX = "oquanta_"


def integration_version() -> str:
    """Return version from manifest.json."""
    manifest_path = Path(__file__).parent / "manifest.json"
    with manifest_path.open(encoding="utf-8") as file:
        payload: dict[str, str] = json.load(file)
    return payload["version"]
