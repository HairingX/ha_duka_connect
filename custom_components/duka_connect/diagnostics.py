"""What a bug report needs: every value with its quality and raw bytes."""

from __future__ import annotations

from typing import Any

from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .const import CONF_DEVICE_ID
from .data import DukaConfigEntry

REDACTED = "**REDACTED**"

REDACTED_SETTINGS = frozenset({CONF_PASSWORD, CONF_HOST, CONF_DEVICE_ID})
"""The credential, and what locates or identifies the unit."""


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: DukaConfigEntry
) -> dict[str, Any]:
    """The client's picture of the unit, without its password, address or device id.

    The entry's unique id is left out: it is the device id.
    """
    client = entry.runtime_data.client
    values: dict[str, Any] = {}
    for name, point in sorted(client.points.items()):
        current = None if point.command else client.value(point.key)
        if current is not None:
            values[name] = {
                "value": str(current.value) if current.value is not None else None,
                "quality": current.quality.name,
                "raw": None if current.raw is None else current.raw.hex(),
                "certainty": point.certainty.name,
            }
    return {
        "entry": {
            "version": entry.version,
            "data": {
                key: REDACTED if key in REDACTED_SETTINGS else setting
                for key, setting in entry.data.items()
            },
        },
        "unit_type": client.unit_type,
        "status": client.status.name,
        "values": values,
    }
