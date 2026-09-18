"""GitHub-backed update entity for Oquanta."""

from __future__ import annotations

import io
import json
import logging
import shutil
import zipfile
from datetime import timedelta
from pathlib import Path
from typing import Any

from aiohttp import ClientTimeout
from awesomeversion import AwesomeVersion
from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, UPDATE_SCAN_HOURS, integration_version

_LOGGER = logging.getLogger(__name__)

GITHUB_HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "Oquanta",
    "X-GitHub-Api-Version": "2022-11-28",
}

ReleaseInfo = dict[str, str | None]


def _empty_release() -> ReleaseInfo:
    return {
        "latest": None,
        "notes": None,
        "zipball": None,
        "html_url": None,
    }


def _release_info(payload: dict[str, Any]) -> ReleaseInfo:
    tag = str(payload.get("tag_name") or "").lstrip("v")
    notes = str(payload.get("body") or "")
    zipball = payload.get("zipball_url")
    html_url = payload.get("html_url")
    return {
        "latest": tag or None,
        "notes": notes[:4000] if notes else None,
        "zipball": str(zipball) if zipball else None,
        "html_url": str(html_url) if html_url else None,
    }


def _awesome_version(tag: str) -> AwesomeVersion | None:
    try:
        return AwesomeVersion(tag)
    except Exception:  # noqa: BLE001
        return None


def newest_published_release(releases: list[Any]) -> dict[str, Any] | None:
    """Pick the newest non-draft GitHub release, including pre-releases."""
    best: dict[str, Any] | None = None
    best_version: AwesomeVersion | None = None
    for item in releases:
        if not isinstance(item, dict) or item.get("draft"):
            continue
        tag = str(item.get("tag_name") or "").lstrip("v")
        if not tag:
            continue
        version = _awesome_version(tag)
        if best is None:
            best = item
            best_version = version
            continue
        if version is None or best_version is None:
            if version is not None:
                best = item
                best_version = version
            continue
        if version > best_version:
            best = item
            best_version = version
    return best


class OquantaUpdateCoordinator(DataUpdateCoordinator[ReleaseInfo]):
    """Poll GitHub Releases for a newer Oquanta version."""

    def __init__(self, hass: HomeAssistant, repo: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="Oquanta",
            update_interval=timedelta(hours=UPDATE_SCAN_HOURS),
        )
        self.repo = repo

    async def _async_update_data(self) -> ReleaseInfo:
        empty = _empty_release()
        if not self.repo:
            return empty
        session = async_get_clientsession(self.hass)
        url = f"https://api.github.com/repos/{self.repo}/releases?per_page=20"
        try:
            async with session.get(
                url, headers=GITHUB_HEADERS, timeout=ClientTimeout(total=20)
            ) as response:
                if response.status == 404:
                    _LOGGER.debug("No GitHub releases yet for %s", self.repo)
                    return empty
                response.raise_for_status()
                payload = await response.json()
        except Exception as err:  # noqa: BLE001 — never break the editor on a failed check
            _LOGGER.warning("Could not check Oquanta updates: %s", err)
            return self.data or empty

        if not isinstance(payload, list) or not payload:
            _LOGGER.debug("No GitHub releases yet for %s", self.repo)
            return empty
        chosen = newest_published_release(payload)
        if chosen is None:
            _LOGGER.debug("No published GitHub releases for %s", self.repo)
            return empty
        return _release_info(chosen)


class OquantaUpdateEntity(UpdateEntity):
    """HA update entity that installs Oquanta from GitHub Releases."""

    _attr_has_entity_name = False
    _attr_name = "Oquanta"
    _attr_unique_id = "oquanta"
    _attr_title = "Oquanta"
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.RELEASE_NOTES
    )
    _attr_entity_picture = None
    _attr_should_poll = False

    def __init__(
        self, hass: HomeAssistant, coordinator: OquantaUpdateCoordinator
    ) -> None:
        self.hass = hass
        self.coordinator = coordinator
        self.entity_id = "update.oquanta"

    @property
    def installed_version(self) -> str:
        return integration_version()

    @property
    def latest_version(self) -> str | None:
        latest = self.coordinator.data.get("latest") if self.coordinator.data else None
        return latest or self.installed_version

    @property
    def release_url(self) -> str | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("html_url")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        stored = self.hass.data.get(DOMAIN, {})
        return {
            "pending_restart": bool(stored.get("pending_restart")),
            "install_error": bool(stored.get("install_error")),
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self) -> None:
        await self.coordinator.async_request_refresh()

    def version_is_newer(self, latest_version: str, installed_version: str) -> bool:
        try:
            return AwesomeVersion(latest_version) > AwesomeVersion(installed_version)
        except Exception:  # noqa: BLE001
            return latest_version != installed_version

    async def async_release_notes(self) -> str | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("notes")

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        del backup, kwargs
        stored = self.hass.data.setdefault(DOMAIN, {})
        stored["install_error"] = False
        self.async_write_ha_state()
        zipball = self.coordinator.data.get("zipball") if self.coordinator.data else None
        if not zipball:
            await self.coordinator.async_request_refresh()
            zipball = (
                self.coordinator.data.get("zipball") if self.coordinator.data else None
            )
        if not zipball:
            stored["install_error"] = True
            self.async_write_ha_state()
            raise RuntimeError("No GitHub release zip available for Oquanta")

        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                zipball, headers=GITHUB_HEADERS, timeout=ClientTimeout(total=120)
            ) as response:
                response.raise_for_status()
                payload = await response.read()
            await self.hass.async_add_executor_job(_install_zip, payload)
        except Exception:
            stored["install_error"] = True
            self.async_write_ha_state()
            raise

        stored["pending_restart"] = True
        stored["install_error"] = False
        self.async_write_ha_state()


def _install_zip(payload: bytes) -> None:
    dest = Path(__file__).parent
    prefix = _oquanta_prefix(payload)
    tmp = dest.parent / ".oquanta_update_tmp"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)

    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for info in archive.infolist():
            name = info.filename.replace("\\", "/")
            if not name.startswith(prefix) or name == prefix:
                continue
            relative = Path(name[len(prefix) :])
            if ".." in relative.parts:
                continue
            target = tmp / relative
            if info.is_dir() or name.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("wb") as out:
                shutil.copyfileobj(source, out)

    _overlay(tmp, dest)
    _prune_stale_panel_js(dest)
    shutil.rmtree(tmp, ignore_errors=True)


def _prune_stale_panel_js(dest: Path) -> None:
    www = dest / "www"
    manifest = dest / "manifest.json"
    if not www.is_dir() or not manifest.is_file():
        return
    try:
        version = json.loads(manifest.read_text(encoding="utf-8"))["version"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return
    keep = f"oquanta-panel.{version}.js"
    for path in www.glob("oquanta-panel*.js"):
        if path.name != keep:
            path.unlink(missing_ok=True)


def _oquanta_prefix(payload: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = [name.replace("\\", "/") for name in archive.namelist()]
    for name in names:
        marker = "custom_components/oquanta/"
        index = name.find(marker)
        if index >= 0:
            return name[: index + len(marker)]
        if name.rstrip("/").endswith("custom_components/oquanta"):
            return f"{name.rstrip('/')}/"
    raise RuntimeError("Zip contains no custom_components/oquanta folder")


def _overlay(source: Path, dest: Path) -> None:
    for path in source.rglob("*"):
        relative = path.relative_to(source)
        target = dest / relative
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
