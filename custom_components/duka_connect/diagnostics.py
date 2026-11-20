"""What a bug report needs to show the unit works: the versions, every value with its quality and
raw bytes, the latest writes with how each ended, and how the unit answers."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, time
from enum import Enum
from importlib import metadata
from typing import Any, cast

from duka_connect import Client, DataValue, Key, PointKey, Status
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import CONF_DEVICE_ID, DOMAIN
from .data import DukaConfigEntry

REDACTED = "**REDACTED**"

REDACTED_SETTINGS = frozenset({CONF_PASSWORD, CONF_HOST, CONF_DEVICE_ID})
"""The credential, and what locates or identifies the unit."""

REDACTED_POINTS = frozenset({PointKey.IP_ADDRESS})
"""The points whose value locates the unit: only whether they were read is kept."""

LIBRARIES = ("duka_connect", "event_connect")
"""The libraries whose installed versions a report names."""


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: DukaConfigEntry
) -> dict[str, Any]:
    """The client's picture of the unit and the writes sent to it, without its password, address
    or device id.

    The entry's unique id is left out: it is the device id. `writes` holds the latest writes of
    each key, the newest last, each with how it ended and the unit's next answer for the key.
    """
    client = entry.runtime_data.client
    integration = await async_get_integration(hass, DOMAIN)
    link = dict(client.diagnostics())
    writes = cast(dict[str, list[dict[str, Any]]], link.pop("writes"))
    return {
        "entry": {
            "version": entry.version,
            "data": {
                key: REDACTED if key in REDACTED_SETTINGS else setting
                for key, setting in entry.data.items()
            },
        },
        "integration_version": None if integration.version is None else str(integration.version),
        "libraries": {name: _version(name) for name in LIBRARIES},
        "model": client.model.name,
        "identity": dict(client.identity),
        "status": {status.name: client.status(status).value for status in Status},
        "seconds_until_next_poll": client.seconds_until_next_poll(),
        "silent": client.silent,
        "silent_for": client.silent_for,
        "values": {
            str(key): _hidden(key, _value(client, key, current))
            for key, current in sorted(client.values.items())
        },
        "unavailable": {
            str(key): reason for key, reason in sorted(client.unavailable_reasons.items())
        },
        "writes": {
            key: [_write(key, record) for record in records] for key, records in writes.items()
        },
        "link": link,
    }


def _value(client: Client, key: Key[Any], current: DataValue[Any]) -> dict[str, Any]:
    """`current`, the value of `key`, as plain data: when the unit last answered it, and how many
    reads of it have failed since."""
    return {
        "value": _plain(current.value),
        "raw": _hex(current.raw),
        "quality": current.quality.name,
        "certainty": str(client.points[key].certainty),
        "at": current.timestamp.isoformat(),
        "consecutive_failures": client.consecutive_failures(key),
    }


def _write(key: str, record: dict[str, Any]) -> dict[str, Any]:
    """The write `record` of `key` with its bytes in hex, its read-back included, and what
    locates the unit left out."""
    read_back = cast(dict[str, Any] | None, record["read_back"])
    return {
        **_hidden(key, {**record, "raw": _hex(record["raw"])}),
        "read_back": None if read_back is None else _hidden(
            key, {**read_back, "raw": _hex(read_back["raw"])}
        ),
    }


def _hidden(key: str, found: dict[str, Any]) -> dict[str, Any]:
    """`found` with its `value` and `raw` left out where `key`'s value locates the unit; a value
    that is None stays, as it says nothing."""
    if found["value"] is None or key not in REDACTED_POINTS:
        return found
    return {**found, "value": REDACTED, "raw": REDACTED}


def _hex(raw: Iterable[int]) -> str | None:
    """The bytes `raw` in hex; None for none."""
    return bytes(raw).hex() or None


def _plain(value: object) -> object:
    """`value` as JSON holds it: a state by its name, a date or time in ISO 8601."""
    if isinstance(value, Enum):
        return value.name
    if isinstance(value, (date, time)):
        return value.isoformat()
    return value


def _version(name: str) -> str | None:
    """The installed version of the package `name`; None if it is not installed."""
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None
