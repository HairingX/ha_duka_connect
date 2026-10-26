"""A simulated Duka One behind the integration, and a config entry for it.

The integration runs the real client; only the unit is simulated, on a local UDP port.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
import pytest_socket
from duka_connect import Client, DiscoveredDevice, discover
from duka_connect.testing import FakeClock, SimulatedDuka
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.duka_connect import const
from custom_components.duka_connect.const import CONF_DEVICE_ID, DOMAIN
from custom_components.duka_connect.data import DukaData

DEVICE_ID = "DUKA0000TEST0001"
PASSWORD = "1111"
NAME = "Duka One"
HOST = "127.0.0.1"
"""The simulated unit listens here, on a port of its own."""


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> Iterator[None]:
    yield


@pytest.fixture(autouse=True)
def no_deprecated_usage(caplog: pytest.LogCaptureFixture) -> Iterator[None]:
    """Fail a test in which Home Assistant reports this integration using something deprecated."""
    yield
    reports = [
        record.getMessage()
        for phase in ("setup", "call")
        for record in caplog.get_records(phase)
        if "Detected that custom integration 'duka_connect'" in record.getMessage()
        or " was used from duka_connect" in record.getMessage()
    ]
    assert reports == []


@pytest.fixture
async def unit() -> AsyncIterator[SimulatedDuka]:
    """The simulated unit, answering; change its values to change what it answers."""
    pytest_socket.enable_socket()
    simulated = SimulatedDuka(device_id=DEVICE_ID, password=PASSWORD)
    await simulated.start(HOST)
    yield simulated
    simulated.close()


@pytest.fixture
def clock() -> FakeClock:
    """The clients' clock: it moves only when a test advances it, so nothing is read by itself.

    Its wall clock starts at the real time, as the unit's clock is set from it.
    """
    return FakeClock(now=dt_util.utcnow())


@pytest.fixture
def network(unit: SimulatedDuka) -> list[SimulatedDuka]:
    """The simulated units on the network, each on a port of its own; add one to add a unit."""
    return [unit]


@pytest.fixture(autouse=True)
def simulated_network(
    monkeypatch: pytest.MonkeyPatch,
    unit: SimulatedDuka,
    network: list[SimulatedDuka],
    clock: FakeClock,
) -> list[Client]:
    """The network the integration sees holds only the simulated units.

    A broadcast reaches every unit, and discovery sent to an address the first; a client
    reaches the unit with its device id. Returns the clients made, in order.
    """
    made: list[Client] = []
    monkeypatch.setattr(const, "DISCOVERY_TIMEOUT", 0.3)

    async def discover_units(
        target: str = "255.255.255.255", *, port: int = 0, timeout: float = 2.0
    ) -> list[DiscoveredDevice]:
        reached = network if target == "255.255.255.255" else network[:1]
        found: list[DiscoveredDevice] = []
        for simulated in reached:
            found += await discover(HOST, port=simulated.port, timeout=timeout)
        return found

    def client(host: str, device_id: str, password: str) -> Client:
        port = next((s.port for s in network if s.device_id == device_id), unit.port)
        made.append(
            Client(host, device_id, password, port=port, timeout=0.2, attempts=1, clock=clock)
        )
        return made[-1]

    monkeypatch.setattr("custom_components.duka_connect.config_flow.discover", discover_units)
    monkeypatch.setattr("custom_components.duka_connect.data.Client", client)
    return made


def entry_data(**changes: Any) -> dict[str, Any]:
    """The data of an entry for the simulated unit."""
    data: dict[str, Any] = {
        CONF_NAME: NAME,
        CONF_HOST: HOST,
        CONF_DEVICE_ID: DEVICE_ID,
        CONF_PASSWORD: PASSWORD,
    }
    data.update(changes)
    return data


@pytest.fixture
def config_entry() -> MockConfigEntry:
    return MockConfigEntry(domain=DOMAIN, title=NAME, unique_id=DEVICE_ID, data=entry_data())


@pytest.fixture
async def loaded(hass: HomeAssistant, config_entry: MockConfigEntry) -> AsyncIterator[DukaData]:
    """The config entry, set up; unloaded again after the test."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    data: DukaData = config_entry.runtime_data
    yield data
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
