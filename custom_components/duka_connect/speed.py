"""The unit's manual speed, 0 to 255, as the percentage Home Assistant shows."""

from __future__ import annotations

import math

from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

# The unit's manual speeds that turn the fan; 0 is shown as 0 %.
_MANUAL_RANGE = (1, 255)


def manual_to_percentage(manual: int) -> int:
    """The percentage a manual speed is shown as."""
    return 0 if manual <= 0 else ranged_value_to_percentage(_MANUAL_RANGE, manual)


def percentage_to_manual(percentage: float) -> int:
    """The manual speed a percentage is written as; one that is not 0 turns the fan."""
    if percentage <= 0:
        return 0
    return math.ceil(percentage_to_ranged_value(_MANUAL_RANGE, percentage))
