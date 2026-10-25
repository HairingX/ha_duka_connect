"""The client behind a config entry, and how one is made."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from duka_connect import Client, Key
from homeassistant.config_entries import ConfigEntry

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


def new_client(host: str, device_id: str, password: str) -> Client:
    """A client for the unit at `host`; not yet connected."""
    return Client(host, device_id, password)


def value[T](client: Client, key: Key[T]) -> T | None:
    """The current value of `key`: None when it was never read or holds no reading."""
    current = client.value(key)
    return current.value if current is not None else None
