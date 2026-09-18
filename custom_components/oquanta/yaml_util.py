"""YAML helpers used by the websocket API and unit tests."""

from __future__ import annotations

from typing import Any

import yaml


def parse_yaml_mapping(text: str) -> dict[str, Any]:
    """Parse Home Assistant YAML into a mapping. Lists become a sequence."""
    parsed = yaml.safe_load(text)
    if isinstance(parsed, list):
        parsed = {"sequence": parsed}
    if not isinstance(parsed, dict):
        raise ValueError("YAML must be a mapping")
    return parsed


def should_skip_empty_draft(graph: dict[str, Any] | None) -> bool:
    """True when a graph has no cards and should not be persisted."""
    if not isinstance(graph, dict):
        return True
    nodes = graph.get("nodes")
    return not isinstance(nodes, list) or len(nodes) == 0
