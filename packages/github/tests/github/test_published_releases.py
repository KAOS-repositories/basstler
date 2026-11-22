"""
Tests for :class:`basstler.github.release_version.PublishedReleases`: which release a
repository has published last, and whether an installed release is behind it.
"""

from __future__ import annotations

import importlib.metadata
from pathlib import Path

import pytest

from basstler.git.commands import GitCommandRunner
from basstler.github.release_version import PublishedReleases, ReleaseVersion

# %% a repository with tags

PUBLISHED_TAGS = ("v1.2.3", "v1.10.0", "v1.9.9", "not-a-release", "v2")
"""
The tags the repository holds: three releases, one other tag and one malformed version.
"""


@pytest.fixture
def published(tmp_path: Path) -> PublishedReleases:
    """
    :return: The releases of a repository carrying :data:`PUBLISHED_TAGS`.
    """
    git = GitCommandRunner(tmp_path)
    git.run("init", "--quiet")
    git.run(
        "-c",
        "user.name=a",
        "-c",
        "user.email=a@example.com",
        "commit",
        "--quiet",
        "--allow-empty",
        "-m",
        "first",
    )
    for tag in PUBLISHED_TAGS:
        git.run("tag", tag)
    return PublishedReleases(git, str(tmp_path))


# %% the latest release


def test_the_latest_release_is_the_highest_version_not_the_last_tag_alphabetically(
    published: PublishedReleases,
):
    assert published.latest() == ReleaseVersion(1, 10, 0)


def test_a_repository_without_releases_has_no_latest_release(tmp_path: Path):
    git = GitCommandRunner(tmp_path)
    git.run("init", "--quiet")
    assert PublishedReleases(git, str(tmp_path)).latest() is None


# %% an installed release behind it


@pytest.mark.parametrize(
    ("installed", "behind"),
    [
        (ReleaseVersion(1, 9, 9), True),
        (ReleaseVersion(1, 10, 0), False),
        (ReleaseVersion(1, 11, 0), False),
        (None, False),
    ],
    ids=["older", "the latest", "newer", "not a release"],
)
def test_an_installed_release_is_behind_only_when_an_older_release(
    published: PublishedReleases, installed: ReleaseVersion | None, behind: bool
):
    assert published.is_ahead_of(installed) is behind


# %% the installed release


@pytest.mark.parametrize(
    ("installed_version", "release"),
    [("3.29.5", ReleaseVersion(3, 29, 5)), ("3.29.6.dev2+gabc123", None)],
    ids=["a release", "a build past one"],
)
def test_the_installed_release_is_read_from_the_package_version(
    monkeypatch: pytest.MonkeyPatch,
    installed_version: str,
    release: ReleaseVersion | None,
):
    monkeypatch.setattr(
        importlib.metadata, "version", lambda distribution: installed_version
    )
    assert ReleaseVersion.installed() == release
