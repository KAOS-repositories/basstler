"""
Tests for finding the names a document cites that this release no longer ships.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from basstler.document_references import (
    PACKAGE_NAME,
    CitedNames,
    Retirement,
    RetiredSkill,
    ShippedModules,
)

from basstler_testing.constants.paths import (
    DatasetLocation,
    RepositoryLocation,
    SkillDirectory,
)

# %% personal notes written against another release

SKILL_NOTES_CITE = "plan-dashboard"
"""
The skill the dataset's notes invoke, which these tests retire in the installed major
release.
"""


def retired_in_installed_major_release() -> dict[str, Retirement]:
    """
    :return: A retirement of the skill the dataset's notes invoke, by that skill's name,
        retired in the installed package's major release.
    """
    return {
        SKILL_NOTES_CITE: Retirement(
            replacement="drop it: the plan site rebuilds on every save",
            major_version=ShippedModules.installed().major_version,
        )
    }


def test_notes_naming_moved_modules_and_a_retired_skill_report_each_of_them():
    notes = DatasetLocation.NOTES_CITING_RETIRED_NAMES.read_text(encoding="utf-8")

    stale = CitedNames.in_text(notes).stale(
        ShippedModules.installed(), retired_in_installed_major_release()
    )

    assert [reference.cited for reference in stale] == [
        f"/{SKILL_NOTES_CITE}",
        f"{PACKAGE_NAME}.no_such_module",
        f"{PACKAGE_NAME}.plan_manifest_tools",
        f"{PACKAGE_NAME}.plan_size_limits",
    ]


def test_a_retired_skill_is_reported_with_what_replaced_it():
    notes = DatasetLocation.NOTES_CITING_RETIRED_NAMES.read_text(encoding="utf-8")

    retirements = retired_in_installed_major_release()

    stale = CitedNames.in_text(notes).stale(ShippedModules.installed(), retirements)

    assert stale[0].replacement == retirements[SKILL_NOTES_CITE].replacement


def test_the_next_major_release_no_longer_reports_a_retired_skill():
    notes = CitedNames.in_text(
        DatasetLocation.NOTES_CITING_RETIRED_NAMES.read_text(encoding="utf-8")
    )
    installed = ShippedModules.installed()
    retirements = retired_in_installed_major_release()
    next_major = replace(
        installed, major_version=retirements[SKILL_NOTES_CITE].major_version + 1
    )

    reported = [reference.cited for reference in notes.stale(next_major, retirements)]

    assert reported == [
        reference.cited
        for reference in notes.stale(installed, retirements)
        if reference.cited != f"/{SKILL_NOTES_CITE}"
    ]


def test_a_module_nothing_replaces_has_no_replacement():
    assert ShippedModules.installed().replacement_for("no_such_module") is None


# %% this repository's own documents


@pytest.mark.parametrize("skill", list(RetiredSkill))
def test_a_retired_skill_is_not_shipped(skill: RetiredSkill):
    skill_directory = (
        RepositoryLocation.PLUGIN.value
        / SkillDirectory.DIRECTORY
        / skill.invoked_as.removeprefix("/")
    )

    assert not skill_directory.exists()


@pytest.mark.parametrize("skill", list(RetiredSkill))
def test_a_retired_skill_is_removed_once_its_major_release_is_superseded(
    skill: RetiredSkill,
):
    assert skill.value.major_version == ShippedModules.installed().major_version
