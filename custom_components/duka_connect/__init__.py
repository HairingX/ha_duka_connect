"""The Duka Connect integration."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from duka_connect import CannotConnectError, Client, Status, UnsupportedDeviceError
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er

from .const import BATTERY_LOW_DEFAULT, CONF_BATTERY_LOW, CONF_DEVICE_ID, DOMAIN, POLL_TICK
from .data import DukaConfigEntry, DukaData, new_client

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.FAN,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: DukaConfigEntry) -> bool:
    """Connect to the unit, create its entities and start reading it."""
    name: str = entry.data[CONF_NAME]
    client = new_client(
        entry.data[CONF_HOST], entry.data[CONF_DEVICE_ID], entry.data[CONF_PASSWORD]
    )
    try:
        await client.connect()
    except CannotConnectError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"name": name},
        ) from err
    except UnsupportedDeviceError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="unsupported_device",
            translation_placeholders={"name": name},
        ) from err

    try:
        entry.runtime_data = DukaData(
            client=client,
            name=name,
            battery_low=int(entry.options.get(CONF_BATTERY_LOW, BATTERY_LOW_DEFAULT)),
        )
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        _remove_lost_entities(hass, entry)
    except BaseException:
        await client.disconnect()
        raise

    entry.async_on_unload(_log_when_unavailable(client, name))
    # Polling starts once the entities have subscribed: the client reads what is wanted.
    entry.runtime_data.poller = entry.async_create_background_task(
        hass, _poll(client), f"{DOMAIN} poll {entry.title}"
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DukaConfigEntry) -> bool:
    """Stop reading the unit and close its connection."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    data = entry.runtime_data
    if data.poller is not None:
        # Stopped before the disconnect, so no read runs against a closing connection.
        data.poller.cancel()
        await asyncio.wait([data.poller])
    await data.client.disconnect()
    return True


def _log_when_unavailable(client: Client, name: str) -> Callable[[], None]:
    """Log once when the unit stops answering, and once when it answers again."""
    answered = True

    @callback
    def status_changed(status: Status) -> None:
        nonlocal answered
        if status is Status.DISCONNECTED and answered:
            _LOGGER.info("%s does not answer", name)
            answered = False
        elif status is Status.CONNECTED and not answered:
            _LOGGER.info("%s answers again", name)
            answered = True

    return client.subscribe_status(status_changed)


@callback
def _remove_lost_entities(hass: HomeAssistant, entry: DukaConfigEntry) -> None:
    """Remove the entities of points the unit no longer has."""
    registry = er.async_get(hass)
    built = entry.runtime_data.unique_ids
    for found in er.async_entries_for_config_entry(registry, entry.entry_id):
        if found.unique_id not in built:
            registry.async_remove(found.entity_id)


async def _poll(client: Client) -> None:
    """Read whatever the client has due, for as long as the entry is loaded."""
    while True:
        try:
            await client.poll()
        except Exception:
            _LOGGER.exception("Reading the unit failed")
            delay = POLL_TICK
        else:
            delay = client.seconds_until_next_poll()
        await asyncio.sleep(POLL_TICK if delay is None else min(delay, POLL_TICK))
