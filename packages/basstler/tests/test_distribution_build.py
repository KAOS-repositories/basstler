"""
Tests for what a release publishes: building every distribution of the workspace at a
tagged commit gives one version, siblings pinned to it, and the licence in each.
"""

from __future__ import annotations

import shutil
import subprocess
import tarfile
import tomllib
import zipfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import pytest
from basstler.git.commands import GitCommandRunner
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from basstler_testing.constants.paths import RepositoryLocation

# %% vocabulary


class ReleaseFile(StrEnum):
    """
    The files every distribution ships beside its code, named as in the repository root.
    """

    LICENSE = "LICENSE"
    NOTICE = "NOTICE"


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

FAMILY = "basstler"
"""
The distribution whose name, alone or followed by a hyphen, names a sibling.
"""

# %% a release built in a scratch repository


@dataclass(frozen=True)
class BuiltRelease:
    """
    The files ``uv build --all-packages`` produced at a tagged commit.
    """

    directory: Path
    """
    Where the wheels and source distributions are.
    """

    @property
    def wheels(self) -> dict[str, Path]:
        """
        The wheels, by the canonical name of the distribution each is of.
        """
        return {
            canonicalize_name(path.name.split("-")[0]): path
            for path in self.directory.glob("*.whl")
        }

    @property
    def source_distributions(self) -> dict[str, Path]:
        """
        The source distributions, by the canonical name of the distribution each is of.
        """
        return {
            canonicalize_name(path.name.rsplit("-", 1)[0]): path
            for path in self.directory.glob("*.tar.gz")
        }


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
    assert set(built_release.wheels) == distribution_names()
    assert set(built_release.source_distributions) == distribution_names()


def test_every_wheel_carries_the_version_of_the_tag(built_release: BuiltRelease):
    """
    All distributions of a release share one version, the tag's.
    """
    versions = {
        path.name.split("-")[1] for path in built_release.wheels.values()
    }

    assert versions == {RELEASE_VERSION}


def requirements_of(wheel: Path) -> list[Requirement]:
    """
    :param wheel: A built wheel.
    :return: The requirements its metadata declares.
    """
    with zipfile.ZipFile(wheel) as archive:
        (metadata,) = (
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        )
        lines = archive.read(metadata).decode("utf-8").splitlines()
    prefix = "Requires-Dist: "
    return [
        Requirement(line.removeprefix(prefix))
        for line in lines
        if line.startswith(prefix)
    ]


def test_every_requirement_on_a_sibling_is_pinned_to_the_release(
    built_release: BuiltRelease,
):
    """
    A release installs together: no distribution accepts a sibling of another version.
    """
    siblings = [
        requirement
        for wheel in built_release.wheels.values()
        for requirement in requirements_of(wheel)
        if canonicalize_name(requirement.name).startswith(FAMILY)
    ]

    assert siblings
    assert {str(requirement.specifier) for requirement in siblings} == {
        f"=={RELEASE_VERSION}"
    }


@pytest.mark.parametrize("release_file", list(ReleaseFile), ids=str)
def test_every_wheel_carries_the_release_files(
    built_release: BuiltRelease, release_file: ReleaseFile
):
    """
    A wheel installed on its own still states its licence and its notices.
    """
    for name, wheel in built_release.wheels.items():
        with zipfile.ZipFile(wheel) as archive:
            carried = {
                Path(entry).name: archive.read(entry)
                for entry in archive.namelist()
                if ".dist-info/licenses/" in entry
            }
        assert carried[release_file] == (
            RepositoryLocation.ROOT.value / release_file
        ).read_bytes(), name


@pytest.mark.parametrize("release_file", list(ReleaseFile), ids=str)
def test_every_source_distribution_carries_the_release_files(
    built_release: BuiltRelease, release_file: ReleaseFile
):
    """
    The files sit at the root of the source distribution, not outside it.
    """
    for name, source in built_release.source_distributions.items():
        with tarfile.open(source) as archive:
            members = archive.getnames()
        assert f"{source.name.removesuffix('.tar.gz')}/{release_file}" in members, name
