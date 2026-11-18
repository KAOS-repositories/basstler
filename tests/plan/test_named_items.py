"""
Tests that an item another plan or a goal names is never removed from under it: a save
refuses the removal, and a landed item stops being named everywhere it is staged.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from basstler.locations import ProjectLocation
from basstler.plan.dependencies import DependencyReference, PlanDirectory
from basstler.plan.exceptions import RemovedItemStillNamed
from basstler.plan.goal import Goal
from basstler.plan.model import ItemStatus, ManifestKey, PlanDocument, PlanManifest
from basstler.plan.size_limits import PlanFiles
from basstler.plan.validation import PlanValidator

from ..constants.paths import DatasetLocation
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

GOAL_IDENTIFIER = "reached"
"""
The goal that may target an item of the plan under test.
"""

# %% writing plans and goals


def removed_reference() -> str:
    """
    :return: The entry naming :data:`REMOVED_ITEM` from another plan or a goal.
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


def write_dependent_plan(plans_directory: Path, **dependencies: list[str]) -> None:
    """
    :param plans_directory: Where every plan's directory lives.
    :param dependencies: The dependent item's dependency lists, keyed by manifest key.
    """
    write_manifest(
        plans_directory,
        minimal_plan(
            id=DEPENDENT_PLAN, items=[manifest_item(DEPENDENT_ITEM, **dependencies)]
        ),
    )


def write_goal(plans_directory: Path, targets: list[str]) -> Path:
    """
    :param plans_directory: Where every plan's directory lives.
    :param targets: The goal's targets.
    :return: The goal's file.
    """
    goal = Goal(identifier=GOAL_IDENTIFIER, title="Reached.", targets=targets)
    path = plans_directory / ProjectLocation.PLAN_GOALS.name / f"{GOAL_IDENTIFIER}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(goal.render())
    return path


def save_problems(plans_directory: Path) -> list:
    """
    :param plans_directory: Where every plan's directory lives, holding the plan under
        test with both items.
    :return: The problems a save of the plan under test without :data:`REMOVED_ITEM`
        carries.
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
        write_dependent_plan(tmp_path, depends_on=[removed_reference()])

        assert save_problems(tmp_path) == [
            RemovedItemStillNamed(
                removed_reference(),
                [DependencyReference(DEPENDENT_ITEM, DEPENDENT_PLAN).text],
            )
        ]

    def test_a_save_refuses_removing_an_item_a_goal_targets(self, tmp_path):
        write_goal(tmp_path, [removed_reference()])

        assert save_problems(tmp_path) == [
            RemovedItemStillNamed(removed_reference(), [GOAL_IDENTIFIER])
        ]

    def test_a_save_removes_an_item_nothing_names(self, tmp_path):
        write_dependent_plan(tmp_path, depends_on=[])

        assert save_problems(tmp_path) == []


# %% staging a plan whose items landed


def stage_landed_plan(plans_directory: Path) -> PlanManifest:
    """
    Stage the plan whose every item landed into *plans_directory*.

    :return: That plan.
    """
    plan = PlanManifest.from_file(DatasetLocation.PLAN_ALL_LANDED)
    destination = plans_directory / plan.identifier
    PlanFiles(
        DatasetLocation.PLAN_ALL_LANDED, DatasetLocation.ROADMAP_OF_STANDING_RULES
    ).stage(
        PlanFiles(
            destination / PlanDocument.MANIFEST, destination / PlanDocument.ROADMAP
        )
    )
    return plan


def landed_references() -> list[str]:
    """
    :return: The entries naming each item of the plan whose every item landed.
    """
    plan = PlanManifest.from_file(DatasetLocation.PLAN_ALL_LANDED)
    assert {item.status for item in plan.items} == {ItemStatus.DONE}
    return [
        DependencyReference(item.identifier, plan.identifier).text
        for item in plan.items
    ]


class TestALandedItemStopsBeingNamed:
    def test_its_goal_targets_drop_it(self, tmp_path):
        still_open = DependencyReference(KEPT_ITEM, DEPENDENT_PLAN).text
        goal_path = write_goal(tmp_path, [*landed_references(), still_open])

        stage_landed_plan(tmp_path)

        assert Goal.from_yaml(goal_path.read_text()).targets == [still_open]

    def test_a_goal_whose_every_target_landed_is_removed(self, tmp_path):
        goal_path = write_goal(tmp_path, landed_references())

        stage_landed_plan(tmp_path)

        assert not goal_path.exists()

    @pytest.mark.parametrize(
        "release_key",
        [ManifestKey.DEPENDS_ON_MERGED, ManifestKey.DEPENDS_ON_PUSHES_DONE],
    )
    def test_its_release_dependencies_drop_it(self, tmp_path, release_key):
        write_dependent_plan(
            tmp_path,
            depends_on=landed_references(),
            **{release_key.key: landed_references()},
        )

        stage_landed_plan(tmp_path)

        (item,) = PlanManifest.from_file(
            tmp_path / DEPENDENT_PLAN / PlanDocument.MANIFEST
        ).items
        assert item.content.get(release_key.key) == []
