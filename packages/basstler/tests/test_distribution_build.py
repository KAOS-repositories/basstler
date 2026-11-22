"""
Tests for what a release publishes: building every distribution of the workspace at a
tagged commit gives one version, siblings pinned to it, and the licence in each.
"""

from __future__ import annotations

import shutil
import subprocess
import tomllib
from enum import StrEnum

import pytest
from basstler.basstler_family import BasstlerFamily
from basstler.git.commands import GitCommandRunner
from basstler.packaging.release import BuiltRelease, ReleaseFile
from packaging.utils import canonicalize_name

from basstler_testing.constants.paths import RepositoryLocation

# %% vocabulary


class WorkspacePart(StrEnum):
    """
    The parts of the repository a release is built from.
    """

    PACKAGES = "packages"
    WORKSPACE_PYPROJECT = "pyproject.toml"
    LOCK = "uv.lock"


RELEASE_TAG = "v7.8.9"
"""
The tag the scratch repository's only commit carries.
"""

RELEASE_VERSION = RELEASE_TAG.removeprefix("v")
"""
The version the build reads from :data:`RELEASE_TAG`.
"""

# %% a release built in a scratch repository


def distribution_names() -> frozenset[str]:
    """
    :return: The canonical name of every distribution the workspace holds.
    """
    return frozenset(
        canonicalize_name(
            tomllib.loads(declaration.read_text(encoding="utf-8"))["project"]["name"]
        )
        for declaration in (
            RepositoryLocation.ROOT.value / WorkspacePart.PACKAGES
        ).glob("*/pyproject.toml")
    )


@pytest.fixture(scope="module")
def built_release(tmp_path_factory: pytest.TempPathFactory) -> BuiltRelease:
    """
    The workspace as it is now, committed and tagged in a scratch repository and built
    the way the publish workflow builds it.
    """
    root = RepositoryLocation.ROOT.value
    scratch = tmp_path_factory.mktemp("release")
    shutil.copytree(
        root / WorkspacePart.PACKAGES,
        scratch / WorkspacePart.PACKAGES,
        ignore=shutil.ignore_patterns("__pycache__", "tests", "*.egg-info"),
    )
    for part in (WorkspacePart.WORKSPACE_PYPROJECT, WorkspacePart.LOCK):
        shutil.copy(root / part, scratch / part)
    for release_file in ReleaseFile:
        shutil.copy(root / release_file, scratch / release_file)
    git = GitCommandRunner(scratch)
    git.run("init", "--quiet")
    git.run("add", "--all")
    git.run(
        "-c",
        "user.name=release",
        "-c",
        "user.email=release@example.com",
        "commit",
        "--quiet",
        "--message",
        "release",
    )
    git.run("tag", RELEASE_TAG)
    out = scratch / "dist"
    subprocess.run(
        ["uv", "build", "--all-packages", "--out-dir", str(out)],
        cwd=scratch,
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    return BuiltRelease(out)


# %% what one release contains


def test_every_distribution_of_the_workspace_is_built(built_release: BuiltRelease):
    """
    Each distribution comes as a wheel and a source distribution.
    """
    assert set(built_release.wheels_by_distribution_name) == distribution_names()
    assert (
        set(built_release.source_distributions_by_distribution_name)
        == distribution_names()
    )


def test_every_wheel_carries_the_version_of_the_tag(built_release: BuiltRelease):
    """
    All distributions of a release share one version, the tag's.
    """
    versions = {
        wheel.version for wheel in built_release.wheels_by_distribution_name.values()
    }

    assert versions == {RELEASE_VERSION}


def test_every_requirement_on_a_sibling_is_pinned_to_the_release(
    built_release: BuiltRelease,
):
    """
    A release installs together: no distribution accepts a sibling of another version.
    """
    siblings = [
        requirement
        for wheel in built_release.wheels_by_distribution_name.values()
        for requirement in wheel.requirements
        if BasstlerFamily().includes_distribution(requirement.name)
    ]

    assert siblings
    assert {str(requirement.specifier) for requirement in siblings} == {
        f"=={RELEASE_VERSION}"
    }


def test_every_wheel_carries_the_licence(built_release: BuiltRelease):
    """
    A wheel installed on its own still states its licence.
    """
    expected = (RepositoryLocation.ROOT.value / ReleaseFile.LICENSE).read_bytes()

    for name, wheel in built_release.wheels_by_distribution_name.items():
        assert wheel.licence == expected, name


def test_every_wheel_carries_the_notice(built_release: BuiltRelease):
    """
    A wheel installed on its own still states its notices.
    """
    expected = (RepositoryLocation.ROOT.value / ReleaseFile.NOTICE).read_bytes()

    for name, wheel in built_release.wheels_by_distribution_name.items():
        assert wheel.notice == expected, name


@pytest.mark.parametrize("release_file", list(ReleaseFile), ids=str)
def test_every_source_distribution_carries_the_release_files(
    built_release: BuiltRelease, release_file: ReleaseFile
):
    """
    The files sit at the root of the source distribution, not outside it.
    """
    for name, source in built_release.source_distributions_by_distribution_name.items():
        assert source.carries_file_at_root(release_file), name
