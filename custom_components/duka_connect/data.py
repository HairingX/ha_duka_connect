"""The client behind a config entry, and how one is made."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field

from duka_connect import Client, Key
from homeassistant.config_entries import ConfigEntry

from .const import BATTERY_LOW_DEFAULT

type DukaConfigEntry = ConfigEntry[DukaData]


@dataclass
class DukaData:
    """What a loaded config entry holds."""

    client: Client
    name: str
    """The unit's name, which every unique id and the device's identifier start with."""
    poller: asyncio.Task[None] | None = field(default=None, repr=False)
    unique_ids: set[str] = field(default_factory=set[str])
    """The unique id of every entity built for the entry, disabled ones included."""
    battery_low: int = BATTERY_LOW_DEFAULT
    """Millivolts under which the clock battery counts as low."""
    battery_low_listeners: list[Callable[[], None]] = field(
        default_factory=list[Callable[[], None]], repr=False
    )

    def set_battery_low(self, millivolts: int) -> None:
        """Set the clock battery's low limit, and tell those who follow it."""
        self.battery_low = millivolts
        for listener in list(self.battery_low_listeners):
            listener()


def new_client(host: str, device_id: str, password: str) -> Client:
    """A client for the unit at `host`; not yet connected."""
    return Client(host, device_id, password)


def value[T](client: Client, key: Key[T]) -> T | None:
    """The current value of `key`: None when it was never read or holds no reading."""
    current = client.value(key)
    return current.value if current is not None else None
