"""The integration against what it is built on: every library point, the translations, the
manifest, the Home Assistant it is tested with, and the quality scale."""

from __future__ import annotations

import importlib.metadata
import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any, cast

import pytest
import yaml
from duka_connect import DUKA_ONE, PointKey
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.helpers.entity import EntityDescription
from packaging.version import Version

from custom_components.duka_connect.binary_sensor import BINARY_SENSORS
from custom_components.duka_connect.button import BUTTONS
from custom_components.duka_connect.const import BATTERY_LOW_KEY, SET_CLOCK_KEY
from custom_components.duka_connect.entity import DukaEntityDescription
from custom_components.duka_connect.number import NUMBERS
from custom_components.duka_connect.select import SELECTS
from custom_components.duka_connect.sensor import SENSORS
from custom_components.duka_connect.switch import SWITCHES

INTEGRATION = Path(__file__).parents[1] / "custom_components" / "duka_connect"
REPOSITORY = INTEGRATION.parents[1]

PLATFORMS: dict[str, tuple[DukaEntityDescription, ...]] = {
    "binary_sensor": BINARY_SENSORS,
    "button": BUTTONS,
    "number": NUMBERS,
    "select": SELECTS,
    "sensor": SENSORS,
    "switch": SWITCHES,
}

NOT_AN_ENTITY: dict[str, str] = {
    str(PointKey.POWER): "the fan entity turns the unit on and off",
    str(PointKey.SPEED): "the fan entity's preset modes and percentage",
    str(PointKey.MANUAL_SPEED): "the fan entity's percentage",
    str(PointKey.CLOCK_TIME): "the unit's clock has no time zone, which a timestamp needs; set by a button",
    str(PointKey.CLOCK_DATE): "the unit's clock has no time zone, which a timestamp needs; set by a button",
}
"""Library points that are no entity of their own, with the reason."""

NOT_DESCRIBED: dict[str, frozenset[str]] = {
    "binary_sensor": frozenset({BATTERY_LOW_KEY}),
    "button": frozenset({SET_CLOCK_KEY}),
    "fan": frozenset({"fan"}),
}
"""Entities built from more than one point, or from none, by platform."""


def _described() -> list[str]:
    return [str(d.point) for descriptions in PLATFORMS.values() for d in descriptions]


def test_every_library_point_is_one_entity_or_has_a_reason_not_to_be() -> None:
    described = _described()
    library = {str(point.key) for point in DUKA_ONE}
    assert len(described) == len(set(described)), "a point with two entities"
    assert library - set(described) - set(NOT_AN_ENTITY) == set()
    assert set(described) | set(NOT_AN_ENTITY) <= library


@pytest.mark.parametrize("platform", list(PLATFORMS))
def test_an_entity_is_named_and_found_by_its_points_key(platform: str) -> None:
    """The key is what an existing installation's unique ids end with."""
    for description in PLATFORMS[platform]:
        assert description.key == description.translation_key == str(description.point)


def _translations(language: str) -> dict[str, Any]:
    path = INTEGRATION / "translations" / f"{language}.json"
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def _paths(tree: Mapping[str, Any], prefix: str = "") -> Iterator[str]:
    """Every leaf of a JSON tree, as its dotted path."""
    for key, value in tree.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            yield from _paths(cast(dict[str, Any], value), path)
        else:
            yield path


def test_danish_translates_exactly_what_english_does() -> None:
    assert set(_paths(_translations("da"))) == set(_paths(_translations("en")))


@pytest.mark.parametrize("platform", [*PLATFORMS, "fan"])
def test_every_entity_has_a_name(platform: str) -> None:
    names = _translations("en")["entity"][platform]
    descriptions: tuple[EntityDescription, ...] = PLATFORMS.get(platform, ())
    expected = {d.translation_key for d in descriptions} | NOT_DESCRIBED.get(platform, frozenset())
    assert expected == set(names)


def test_every_icon_belongs_to_a_translated_entity() -> None:
    icons = json.loads((INTEGRATION / "icons.json").read_text(encoding="utf-8"))
    names = _translations("en")["entity"]
    for platform, entities in icons["entity"].items():
        for key in entities:
            assert key in names[platform], f"{platform}.{key}"


def _manifest() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))
    return loaded


def _released(version: str) -> bool:
    """Whether `version` can be a release: one built from a branch carries a local part, such as
    `+g1c7097c`, which PyPI refuses."""
    return Version(version).local is None


def test_a_library_built_from_a_branch_is_not_a_release() -> None:
    assert _released("0.2.0")
    assert not _released("0.2.1.dev3+g1c7097c")


def test_the_manifest_pins_the_library_version_the_tests_run() -> None:
    installed = importlib.metadata.version("duka_connect")
    if not _released(installed):
        pytest.skip(f"duka_connect {installed} is built from a branch, so no release pins it yet")
    assert _manifest()["requirements"] == [f"duka_connect=={installed}"]


def test_the_test_requirements_pin_what_the_manifest_requires() -> None:
    lines = (REPOSITORY / "requirements-test.txt").read_text(encoding="utf-8").splitlines()
    assert [line for line in lines if line.startswith("duka_connect==")] == _manifest()["requirements"]


def test_hacs_requires_the_home_assistant_the_tests_run() -> None:
    hacs = json.loads((REPOSITORY / "hacs.json").read_text(encoding="utf-8"))
    assert hacs["homeassistant"] == HA_VERSION


def test_the_library_is_imported_from_its_package_not_from_the_integration() -> None:
    """The integration's folder has the library's name."""
    import duka_connect

    assert INTEGRATION not in Path(duka_connect.__file__).parents


QUALITY_SCALE_RULES = frozenset({
    # Bronze
    "action-setup", "appropriate-polling", "brands", "common-modules",
    "config-flow-test-coverage", "config-flow", "dependency-transparency", "docs-actions",
    "docs-conditions", "docs-high-level-description", "docs-installation-instructions",
    "docs-removal-instructions", "docs-triggers", "entity-event-setup", "entity-unique-id",
    "has-entity-name", "runtime-data", "test-before-configure", "test-before-setup",
    "unique-config-entry",
    # Silver
    "action-exceptions", "config-entry-unloading", "docs-configuration-parameters",
    "docs-installation-parameters", "entity-unavailable", "integration-owner",
    "log-when-unavailable", "parallel-updates", "reauthentication-flow", "test-coverage",
    # Gold
    "devices", "diagnostics", "discovery-update-info", "discovery", "docs-data-update",
    "docs-examples", "docs-known-limitations", "docs-supported-devices",
    "docs-supported-functions", "docs-troubleshooting", "docs-use-cases", "dynamic-devices",
    "entity-category", "entity-device-class", "entity-disabled-by-default",
    "entity-translations", "exception-translations", "icon-translations",
    "reconfiguration-flow", "repair-issues", "stale-devices",
    # Platinum
    "async-dependency", "inject-websession", "strict-typing",
})
"""The rules of Home Assistant's Integration Quality Scale, as its developer documentation lists
them. hassfest does not check this file for a custom integration, so this test does."""


def test_the_quality_scale_states_every_rule_and_explains_every_exemption() -> None:
    text = (INTEGRATION / "quality_scale.yaml").read_text(encoding="utf-8")
    rules = cast(dict[str, Any], yaml.safe_load(text)["rules"])
    assert set(rules) == QUALITY_SCALE_RULES
    for rule, state in rules.items():
        if state == "done":
            continue
        assert isinstance(state, dict), rule
        entry = cast(dict[str, Any], state)
        assert entry["status"] in ("done", "exempt", "todo"), rule
        if entry["status"] != "done":
            assert entry.get("comment"), f"{rule} is {entry['status']} without a reason"
