"""Constants for the Duka Connect integration."""

from typing import Final

DOMAIN: Final = "duka_connect"

CONF_DEVICE_ID: Final = "device_id"
"""The id Duka's app shows for the unit; it is the entry's unique id."""

DEFAULT_NAME: Final = "Duka One"
"""What a unit is called unless the user names it: every unique id starts with the name, so the
entities keep theirs when the unit is replaced."""

DISCOVERY_TIMEOUT: Final = 2.0
"""Seconds to wait for units to answer a discovery."""

POLL_TICK: Final = 1.0
"""Longest wait, in seconds, between two calls to the client's poll.

The client plans every read itself, and a poll with nothing due sends nothing. The wait is
capped because a new subscription can make a point due while the loop sleeps.
"""
