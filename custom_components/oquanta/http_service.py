"""Outbound HTTP request service for Oquanta HTTP cards."""

from __future__ import annotations

import json
import logging
from typing import Any

DOMAIN = "oquanta"

_LOGGER = logging.getLogger(__name__)

SERVICE_HTTP_REQUEST = "http_request"

HTTP_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD")


def normalize_headers(value: object) -> dict[str, str]:
    """Turn service headers into a string map."""
    if value is None or value == "":
        return {}
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return {}
        parsed = json.loads(stripped)
        if not isinstance(parsed, dict):
            raise ValueError("headers must be an object")
        value = parsed
    if not isinstance(value, dict):
        raise ValueError("headers must be a mapping")
    return {str(key): str(item) for key, item in value.items()}


def aiohttp_body(payload: object) -> dict[str, Any]:
    """Pick json= or data= for aiohttp from a service payload."""
    if payload is None or payload == "":
        return {}
    if isinstance(payload, (dict, list)):
        return {"json": payload}
    if isinstance(payload, str):
        stripped = payload.strip()
        if not stripped:
            return {}
        if stripped[:1] in "{[":
            try:
                return {"json": json.loads(stripped)}
            except json.JSONDecodeError:
                return {"data": payload}
        return {"data": payload}
    return {"data": str(payload)}


def async_register(hass: Any) -> None:
    """Register oquanta.http_request."""
    import voluptuous as vol
    from homeassistant.core import ServiceCall, ServiceResponse, SupportsResponse
    from homeassistant.helpers import config_validation as cv

    schema = vol.Schema(
        {
            vol.Required("url"): cv.string,
            vol.Optional("method", default="GET"): vol.All(
                cv.string,
                vol.Upper,
                vol.In(HTTP_METHODS),
            ),
            vol.Optional("headers"): vol.Any(dict, cv.string),
            vol.Optional("payload"): vol.Any(dict, list, cv.string, None),
            vol.Optional("timeout", default=10): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=120)
            ),
        }
    )

    async def _handle(call: ServiceCall) -> ServiceResponse:
        return await async_handle_http_request(hass, call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_HTTP_REQUEST,
        _handle,
        schema=schema,
        supports_response=SupportsResponse.OPTIONAL,
    )


async def async_handle_http_request(hass: Any, call: Any) -> dict[str, Any]:
    """Perform the HTTP request on the Home Assistant host."""
    import aiohttp
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    url = str(call.data["url"]).strip()
    method = str(call.data.get("method", "GET")).upper()
    timeout = int(call.data.get("timeout", 10))
    headers = normalize_headers(call.data.get("headers"))
    body = aiohttp_body(call.data.get("payload"))
    session = async_get_clientsession(hass)
    timeout_cfg = aiohttp.ClientTimeout(total=timeout)
    async with session.request(method, url, headers=headers, timeout=timeout_cfg, **body) as response:
        text = await response.text()
        _LOGGER.debug(
            "oquanta.http_request %s %s -> %s",
            method,
            url,
            response.status,
        )
        return {
            "status": response.status,
            "ok": response.ok,
            "url": str(response.url),
            "body": text[:8000],
        }


def async_unregister(hass: Any) -> None:
    """Remove oquanta.http_request if present."""
    hass.services.async_remove(DOMAIN, SERVICE_HTTP_REQUEST)
