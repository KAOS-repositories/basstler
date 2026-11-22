"""
Tests for github/basstler_project.py: basstler's own repository, read from the installed
package's metadata.
"""

from __future__ import annotations

import importlib.metadata

from basstler.github.basstler_project import BasstlerProject, ProjectUrlLabel
from basstler.locations import PackageLocation
from basstler.package_map import Distribution

# %% the repository


def test_the_repository_is_the_one_the_package_metadata_names_as_its_source():
    labelled = dict(
        entry.split(", ", 1)
        for entry in importlib.metadata.metadata(Distribution.GITHUB).get_all(
            "Project-URL"
        )
    )
    assert BasstlerProject.repository.url == labelled[ProjectUrlLabel.SOURCE]


def test_the_name_is_the_package_s_own():
    assert BasstlerProject.name == PackageLocation.DIRECTORY.name
