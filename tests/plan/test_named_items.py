"""
Tests that a save never removes an item another plan still names.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from basstler.plan.dependencies import DependencyReference, PlanDirectory
from basstler.plan.exceptions import RemovedItemStillNamed
from basstler.plan.model import ManifestKey, PlanDocument
from basstler.plan.validation import PlanValidator

from ..manifest_builders import PLAN_UNDER_TEST_ID, manifest_item, minimal_plan

KEPT_ITEM = "kept"
"""
The item every save of the plan under test keeps.
"""

REMOVED_ITEM = "removed"
"""
The item a save of the plan under test removes.
"""

DEPENDENT_PLAN = "dependent-plan"
"""
The other plan, whose single item may depend on the plan under test.
"""

DEPENDENT_ITEM = "dependent"
"""
The single item of :data:`DEPENDENT_PLAN`.
"""

# %% writing plans


def removed_reference() -> str:
    """
    :return: The entry naming :data:`REMOVED_ITEM` from another plan.
    """
    return DependencyReference(
        item_identifier=REMOVED_ITEM, plan_id=PLAN_UNDER_TEST_ID
    ).text


def write_manifest(plans_directory: Path, manifest: dict) -> None:
    """
    :param plans_directory: Where every plan's directory lives.
    :param manifest: The plan to write under its own id.
    """
    path = (
        plans_directory / manifest[ManifestKey.IDENTIFIER.key] / PlanDocument.MANIFEST
    )
    path.parent.mkdir(parents=True)
    path.write_text(yaml.safe_dump(manifest))


def write_dependent_plan(plans_directory: Path, depends_on: list[str]) -> None:
    """
    :param plans_directory: Where every plan's directory lives.
    :param depends_on: The dependent item's ``depends_on``.
    """
    write_manifest(
        plans_directory,
        minimal_plan(
            id=DEPENDENT_PLAN,
            items=[manifest_item(DEPENDENT_ITEM, depends_on=depends_on)],
        ),
    )


def save_problems(plans_directory: Path) -> list:
    """
    :param plans_directory: Where every plan's directory lives.
    :return: The problems a save of the plan under test without :data:`REMOVED_ITEM`
        carries, its saved copy holding both items.
    """
    write_manifest(
        plans_directory,
        minimal_plan(items=[manifest_item(KEPT_ITEM), manifest_item(REMOVED_ITEM)]),
    )
    return PlanValidator(
        minimal_plan(items=[manifest_item(KEPT_ITEM)]),
        PlanDirectory(plans_directory),
        saved_item_identifiers=frozenset({KEPT_ITEM, REMOVED_ITEM}),
    ).problems


# %% a save that removes a named item


class TestRemovingANamedItem:
    def test_a_save_refuses_removing_an_item_another_plan_depends_on(self, tmp_path):
        write_dependent_plan(tmp_path, [removed_reference()])

        assert save_problems(tmp_path) == [
            RemovedItemStillNamed(
                removed_reference(),
                [DependencyReference(DEPENDENT_ITEM, DEPENDENT_PLAN).text],
            )
        ]

    def test_a_save_removes_an_item_nothing_names(self, tmp_path):
        write_dependent_plan(tmp_path, [])

        assert save_problems(tmp_path) == []
