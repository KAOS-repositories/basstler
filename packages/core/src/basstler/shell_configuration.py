"""
Calls into the plugin's shell configuration, ``resolve-personal-notes-config.sh``.

The shell configuration is where the personal-notes remote and branch precedence is
decided. A module that needs one of its answers sources it and calls its function,
rather than re-deriving the precedence, so the module and the hook scripts can never
disagree. This is the one place that does so.
"""

from __future__ import annotations

import dataclasses
import os
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, StrEnum
from pathlib import Path, PurePath, PurePosixPath

from basstler.bash import Bash
from basstler.locations import PluginLocation, ProjectLocation
from basstler.plugin_root import PluginRoot


class FetchedBranchReference(StrEnum):
    """
    Where the shell configuration keeps a branch it fetched, so a later fetch of
    anything else never moves it the way it moves ``FETCH_HEAD``.
    """

    PERSONAL_NOTES = "refs/basstler/personal-notes"
    """
    The personal-notes branch, as
    :attr:`ShellConfigurationFunction.FETCH_PERSONAL_NOTES_BRANCH` last fetched it; the
    shell configuration's ``PERSONAL_NOTES_REFERENCE``.
    """

    def file_at(self, path: str | PurePath) -> str:
        """
        :param path: A file's path relative to the branch's root.
        :return: The git object name of that file on the fetched branch, its path
            ``/``-separated on every platform.
        """
        return f"{self}:{PurePosixPath(path)}"


class ShellConfigurationFunction(StrEnum):
    """
    The functions of the shell configuration, named once here for every caller.
    """

    FETCH_PERSONAL_NOTES_BRANCH = "fetch_personal_notes_branch"
    """
    Fetches the personal-notes branch into
    :attr:`FetchedBranchReference.PERSONAL_NOTES`.

    Falls back to the current branch's upstream remote when the configured one does not
    carry the branch.
    """

    RECORDED_GIT_IDENTITY = "recorded_git_identity"
    """
    Prints the commit identity the personal-notes branch records, as its name and email
    separated by a tab.
    """

    PLAN_ID_FOR_BRANCH = "plan_id_for_branch"
    """
    Prints the plan the fetched branch index says tracks the branch it is given, and
    nothing when no plan does.
    """

    RECORD_BASSTLER_PROJECT = "record_basstler_project"
    """
    Records, in the package's environment, the project directory it belongs to.
    """

    REPOSITORY_NAME = "repository_name"
    """
    Prints the project's ``origin`` as ``owner/repo``.
    """

    PLAN_SITE_PAGE_URL = "plan_site_page_url"
    """
    Prints the address of the project's page on the plan site, of one of its plans, or
    of one item's card, and fails when the fetched hub file names no site or the lookup
    fails, the lookup's error going to stderr.
    """

    BASSTLER_PACKAGE_SOURCE = "basstler_package_source"
    """
    Prints what the package is installed from: the checkout the plugin sits in, else its
    repository at the plugin's own release.
    """

    BASSTLER_INSTALL_COMMAND = "basstler_install_command"
    """
    Sets the command installing the package into its environment, from the checkout or
    the plugin's release.
    """

    BASSTLER_BRANCH_OR_TAG = "basstler_branch_or_tag"
    """
    Prints the basstler branch or tag the package is installed at outside a checkout:
    the plugin's own release, else ``main``.
    """

    PLUGIN_CONTENT_DIGEST = "plugin_content_digest"
    """
    Prints a checksum of the plugin's hooks, skills and manifest, which changes whenever
    the plugin is synced at another commit.
    """

    READY_BASSTLER_PYTHON = "ready_basstler_python"
    """
    Returns once the package is installed and current for the plugin running it,
    installing it first where it is not, and exits the caller when it still cannot run.
    """

    def run(
        self, project_root: Path | None = None, *arguments: str
    ) -> subprocess.CompletedProcess[str]:
        """
        Source the shell configuration and call this function.

        :param project_root: The repository to run within; the current directory if not
            given.
        :param arguments: The arguments to call the function with.
        :return: The completed process, with output captured as text.
        """
        configuration = PluginRoot.locate(os.environ).path_of(
            PluginLocation.PERSONAL_NOTES_CONFIGURATION_SCRIPT
        )
        return subprocess.run(
            Bash.locate(os.environ).command(
                "-c",
                f'source "{configuration}" && {self} "$@"',
                PluginLocation.PERSONAL_NOTES_CONFIGURATION_SCRIPT.name,
                *arguments,
            ),
            cwd=project_root,
            capture_output=True,
            encoding="utf-8",
        )


# %% reading a value out of the clone


def git_value(project_root: Path, *arguments: str) -> str | None:
    """
    Read a value git can answer for a clone, or nothing when it has no answer.

    An absent answer is an ordinary outcome here - an unset configuration key, a remote
    the clone never added - so it is reported rather than raised, and every caller in
    this module falls through to the next thing it knows.

    :param project_root: The clone to run in.
    :param arguments: The git subcommand and its arguments.
    :return: The trimmed output, or ``None`` when the command failed or said nothing.
    """
    completed = subprocess.run(
        ["git", *arguments],
        cwd=project_root,
        capture_output=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


# %% the settings whose values the printed steps depend on


@dataclass(frozen=True)
class PersonalNotesSettingSpecification:
    """
    Where one personal-notes setting is read from, and what it falls back to.

    resolve-personal-notes-config.sh is the definition of both the precedence and the
    defaults; this mirrors them because the shell file exports nothing a child process
    could read them from.
    """

    git_config_key: str
    """
    The git config key that takes precedence over everything else.
    """

    environment_variable: str
    """
    The environment variable read when no git config value is set.
    """

    default: str
    """
    The value in force when neither of the two above is set.
    """

    def resolve(self, project_root: Path, environment: Mapping[str, str]) -> str:
        """
        Read this setting's value as the hooks themselves would.

        :param project_root: The clone whose git config to read.
        :param environment: The environment to read the variable from.
        :return: The value in force.
        """
        configured = git_value(project_root, "config", "--get", self.git_config_key)
        if configured is not None:
            return configured
        return environment.get(self.environment_variable) or self.default


class PersonalNotesSetting(PersonalNotesSettingSpecification, Enum):
    """
    The three settings that decide where personal notes live, in the order the printed
    variable list uses them.

    Each member *is* a specification, so a setting's own key, variable and default are
    reached directly and no caller holds a parallel list of them.

    .. note::
       Both :meth:`__new__` and :meth:`__init__` are needed: the enum machinery builds a
       member's value by calling the mixed-in type with the member's value as arguments,
       which a specification with no defaulted field cannot survive.
    """

    def __new__(
        cls, specification: PersonalNotesSettingSpecification
    ) -> PersonalNotesSetting:
        """
        Make the member without letting the enum rebuild the specification from it.

        :param specification: Where this setting is read from.
        :return: The member, carrying that specification as its value.
        """
        member = object.__new__(cls)
        member._value_ = specification
        return member

    def __init__(self, specification: PersonalNotesSettingSpecification) -> None:
        """
        Carry the specification's values on the member itself.

        :param specification: Where this setting is read from.
        """
        for field in dataclasses.fields(PersonalNotesSettingSpecification):
            object.__setattr__(self, field.name, getattr(specification, field.name))

    REMOTE = PersonalNotesSettingSpecification(
        git_config_key="claude.personalNotesRemote",
        environment_variable="CLAUDE_PERSONAL_NOTES_REMOTE",
        default="origin",
    )
    """
    The remote, or raw URL, the notes branch lives on.
    """

    BRANCH = PersonalNotesSettingSpecification(
        git_config_key="claude.personalNotesBranch",
        environment_variable="CLAUDE_PERSONAL_NOTES_BRANCH",
        default="claude/personal-notes",
    )
    """
    The branch the notes are stored on.
    """

    PATH = PersonalNotesSettingSpecification(
        git_config_key="claude.personalNotesPath",
        environment_variable="CLAUDE_PERSONAL_NOTES_PATH",
        default=ProjectLocation.PERSONAL_NOTES_DOCUMENT.as_posix(),
    )
    """
    Where on that branch the notes file sits.
    """
