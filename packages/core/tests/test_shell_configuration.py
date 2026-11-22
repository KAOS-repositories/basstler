"""
Tests for naming files on the branches the shell configuration fetches, and for the
personal-notes settings it resolves.
"""

from __future__ import annotations

import subprocess
from pathlib import Path, PureWindowsPath

import pytest

from basstler.locations import PluginLocation, ProjectLocation
from basstler.text_file import TextFile
from basstler.shell_configuration import (
    FetchedBranchReference,
    PersonalNotesSetting,
    git_value,
)

from basstler_testing.constants.paths import RepositoryLocation

FORK_REMOTE_URL = "https://github.com/some-user/some-repository.git"
"""
The GitHub URL the fork's ``origin`` names.
"""

RESOLVE_CONFIG_SCRIPT = (
    RepositoryLocation.HOOKS / PluginLocation.PERSONAL_NOTES_CONFIGURATION_SCRIPT.name
)
"""
The shell configuration the hooks source.
"""


def run_git(clone: Path, *arguments: str) -> None:
    """
    :param clone: The clone to run in.
    :param arguments: The git subcommand and its arguments.
    """
    subprocess.run(["git", *arguments], cwd=clone, check=True, encoding="utf-8")


@pytest.fixture
def clone(tmp_path: Path) -> Path:
    """
    :param tmp_path: pytest's per-test temporary directory.
    :return: An initialized clone with no remote and no settings of its own.
    """
    run_git(tmp_path, "init", "--quiet")
    return tmp_path


@pytest.fixture
def clone_with_fork_remote(clone: Path) -> Path:
    """
    :param clone: The clone to add the remote to.
    :return: The same clone, its ``origin`` naming a GitHub URL.
    """
    run_git(clone, "remote", "add", "origin", FORK_REMOTE_URL)
    return clone


# %% git tree paths


def test_a_file_on_the_fetched_branch_is_named_with_slashes_from_a_windows_path():
    """
    Git names a file in a tree with ``/`` on every platform, so a path Windows built
    with ``\\`` names no file.
    """
    windows_path = PureWindowsPath(*ProjectLocation.PERSONAL_PLAN_ITEM_MODES.parts)

    assert FetchedBranchReference.PERSONAL_NOTES.file_at(windows_path) == (
        f"{FetchedBranchReference.PERSONAL_NOTES}:"
        f"{ProjectLocation.PERSONAL_PLAN_ITEM_MODES.as_posix()}"
    )


# %% reading a value out of the clone


def test_a_value_git_cannot_answer_is_reported_rather_than_raised(
    clone: Path,
) -> None:
    """
    Both callers fall through to something else when git has no answer, so an unset key
    and an unknown remote have to come back as nothing at all.
    """
    root = clone
    assert git_value(root, "config", "--get", "claude.notSet") is None
    assert git_value(root, "remote", "get-url", "no-such-remote") is None


def test_a_value_git_does_answer_comes_back_trimmed(
    clone_with_fork_remote: Path,
) -> None:
    """
    The answer is the value itself, without the newline git writes after it.
    """
    root = clone_with_fork_remote
    assert git_value(root, "remote", "get-url", "origin") == FORK_REMOTE_URL


# %% the personal-notes settings


def test_git_config_outranks_the_environment(
    clone: Path,
) -> None:
    """
    The precedence the hooks apply - git config, then environment, then default.
    """
    run_git(
        clone, "config", PersonalNotesSetting.PATH.git_config_key, "configured/notes.md"
    )
    resolved = PersonalNotesSetting.PATH.resolve(
        clone,
        {PersonalNotesSetting.PATH.environment_variable: "environment/notes.md"},
    )
    assert resolved == "configured/notes.md"


def test_the_settings_are_the_ones_the_hooks_resolve() -> None:
    """
    Every key, variable and default named here is named by resolve-personal-notes-
    config.sh, which is what the hooks themselves read.
    """
    configuration = TextFile(RESOLVE_CONFIG_SCRIPT).read()
    missing = [
        value
        for setting in PersonalNotesSetting
        for value in (
            setting.git_config_key,
            setting.environment_variable,
            setting.default,
        )
        if value not in configuration
    ]
    assert missing == []
