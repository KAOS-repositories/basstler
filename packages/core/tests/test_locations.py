"""
The paths the package names, and how a member stands in for its path.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

import pytest

from basstler.locations import (
    INSTALLED_PACKAGE,
    PackageLocation,
    PluginLocation,
    ProjectLocation,
    WorkspaceLocation,
)

# %% a member stands in for its path


@pytest.mark.parametrize(
    "location", list(ProjectLocation), ids=lambda member: member._name_
)
def test_a_member_formats_as_its_path(location: ProjectLocation):
    """
    Members are written into ``git`` references, ``bash -c`` lines and reports as text,
    where an enumeration's own formatting would print its name.
    """
    assert f"{location}" == str(location.value)


def test_a_member_is_accepted_where_a_path_is(tmp_path: Path):
    """
    Joining onto a root, joining beneath a member and handing one to ``os`` all see the
    path.
    """
    assert (
        tmp_path / ProjectLocation.PERSONAL_NOTES
        == tmp_path / ProjectLocation.PERSONAL_NOTES.value
    )
    assert (
        ProjectLocation.PERSONAL_NOTES / "a.md"
        == ProjectLocation.PERSONAL_NOTES.value / "a.md"
    )
    assert os.fspath(ProjectLocation.PERSONAL_NOTES) == str(
        ProjectLocation.PERSONAL_NOTES.value
    )


@pytest.mark.parametrize(
    "location", list(ProjectLocation), ids=lambda member: member._name_
)
def test_a_member_is_its_path(location: ProjectLocation):
    """
    A member is the path it names, so any ``Path`` method reads it directly.
    """
    assert isinstance(location, Path)
    assert location == location.value


def test_a_path_derived_from_a_member_is_a_plain_path():
    """
    Joining, taking a parent or a sibling builds a new path rather than looking up a
    member that does not exist.
    """
    derived = (
        ProjectLocation.PERSONAL_NOTES / "a.md",
        ProjectLocation.PERSONAL_NOTES.parent,
        ProjectLocation.PERSONAL_NOTES.with_name("other"),
    )

    assert [type(path) for path in derived] == [type(Path())] * len(derived)


def test_members_hash_as_their_paths():
    """
    A member and its path are one key, as two equal paths are.
    """
    assert {ProjectLocation.PERSONAL_NOTES: True}[ProjectLocation.PERSONAL_NOTES.value]


# %% the package's own files


def test_the_package_directory_is_a_part_of_the_package_imported():
    """
    The core distribution's directory is one the ``basstler`` package is imported from.
    """
    assert PackageLocation.DIRECTORY.value in INSTALLED_PACKAGE.directories


def test_the_package_directory_sits_under_its_distributions_src_directory():
    """
    Each distribution follows the ``src`` layout under ``packages`` of the workspace.
    """
    assert PackageLocation.DIRECTORY.value.parent.parent.parent == (
        PackageLocation.SOURCE_TREE / WorkspaceLocation.PACKAGES
    )


def test_the_meta_package_metadata_names_the_package_s_own_distribution():
    """
    The metadata a checkout's requirements start from is that of the distribution the
    package is named after.
    """
    metadata = tomllib.loads(
        PackageLocation.META_PACKAGE_METADATA.value.read_text(encoding="utf-8")
    )

    assert metadata["project"]["name"] == PackageLocation.DIRECTORY.value.name


# %% the plugin's files


def test_the_plugin_scripts_are_under_its_hooks_directory():
    """
    Every script the package runs is one of the plugin's hooks.
    """
    assert {
        location.parent
        for location in PluginLocation
        if location is not PluginLocation.HOOKS
    } == {PluginLocation.HOOKS.value}
