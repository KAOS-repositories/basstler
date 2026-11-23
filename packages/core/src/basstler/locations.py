"""
Every file and directory this package names, each written once.

..note:: Imports nothing outside the standard library, since :mod:`basstler.setup.dependencies`
    reads its declaration's location from here before anything is installed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import ReprEnum
from pathlib import Path

import basstler
from basstler.environment import EnvironmentVariable


class PathEnumeration(Path, ReprEnum):
    """
    An enumeration whose members are paths.

    A member is the path it names - joined onto another with ``/``, opened, passed to a
    subprocess, formatted as its text - and every path derived from one is a plain
    :class:`~pathlib.Path`.

    ..warning:: ``Path.name`` shadows the enumeration's own ``name``: ``member.name`` is
        the path's last component, and the member's name is ``member._name_``.
    """

    def __hash__(self) -> int:
        """
        Hash as the path does, so a member and its path are one key; the enumeration's own
        hash would tell them apart.
        """
        return hash(self.value)

    def __eq__(self, value: object, /) -> bool:
        """
        The value of the Enum should be equal to an equivalent Path instance.

        :param value: A Path instance to compare.
        :return: True if the value is equal to an equivalent Path instance, False otherwise.
        """
        return self.value == value

    def with_segments(self, *path_segments: str | os.PathLike[str]) -> Path:
        """
        :param path_segments: The segments of a path derived from this one.
        :return: That path, as a plain path rather than a lookup of a member by value.
        """
        return Path(*path_segments)


class ShippedPath(PathEnumeration):
    """
    The files and directories the distributions ship inside the ``basstler`` package,
    relative to it.
    """

    TEMPLATES = Path("templates")
    """
    The templates pages, workflows and instruction files are rendered from; each
    distribution ships the templates it renders.
    """

    STACK_CONFIGURATION = Path("github") / "stack.toml"
    """
    The shipped stack configuration every run starts from, before a project's and a
    user's overrides.
    """

    UPSTREAM_REVIEWS_FETCH = Path("upstream_reviews") / "helper" / "fetch.py"
    """
    The program a helper session runs without ``basstler``, so it imports nothing of it.
    """


@dataclass(frozen=True)
class NamespacePackage:
    """
    The parts of the ``basstler`` namespace package, one for each installed distribution
    or a single one where they are installed into one directory.
    """

    directories: tuple[Path, ...]
    """
    Each part's directory, in the order imports search them.
    """

    def shipped(self, path: Path) -> Path:
        """
        :param path: A path relative to the package.
        :return: *path* in the first part shipping it; in the first part when none does.
        """
        return next(
            (
                directory / path
                for directory in self.directories
                if (directory / path).exists()
            ),
            self.directories[0] / path,
        )

    def every(self, path: Path) -> tuple[Path, ...]:
        """
        :param path: A path relative to the package.
        :return: *path* in every part shipping it, in the order imports search them.
        """
        return tuple(
            directory / path
            for directory in self.directories
            if (directory / path).exists()
        )


INSTALLED_PACKAGE = NamespacePackage(tuple(Path(entry) for entry in basstler.__path__))
"""
The parts of the ``basstler`` package this interpreter imports.
"""


class WorkspaceLocation(PathEnumeration):
    """
    The parts of the uv workspace of basstler's distributions.
    """

    PACKAGES = Path("packages")
    """
    The directory holding a directory for each distribution, relative to the root.
    """

    METADATA = Path("pyproject.toml")
    """
    The metadata of the workspace, relative to its root, and of each distribution,
    relative to its directory.
    """

    PACKAGE_SOURCE = Path("src") / "basstler"
    """
    A distribution's part of the ``basstler`` package, relative to its directory.
    """

    LOCK = Path("uv.lock")
    """
    The versions every distribution and requirement of the workspace installs at,
    relative to the root.
    """


class PackageLocation(PathEnumeration):
    """
    The core distribution's own directory, the files the distributions ship, and the
    checkout they are imported from, as absolute paths.
    """

    DIRECTORY = Path(__file__).parent
    """
    The core distribution's part of the ``basstler`` package.
    """

    SOURCE_TREE = DIRECTORY.parents[3]
    """
    The checkout's root, holding the workspace's ``pyproject.toml`` and ``packages``,
    when the package is imported from a checkout through an editable install.
    Meaningless for a package installed as a copy.
    """

    STACK_CONFIGURATION = INSTALLED_PACKAGE.shipped(ShippedPath.STACK_CONFIGURATION)
    """
    :attr:`ShippedPath.STACK_CONFIGURATION`, where the github distribution ships it.
    """

    LICENSE = SOURCE_TREE / "LICENSE"
    """
    The licence text of a checkout.
    """

    UPSTREAM_REVIEWS_FETCH = INSTALLED_PACKAGE.shipped(
        ShippedPath.UPSTREAM_REVIEWS_FETCH
    )
    """
    :attr:`ShippedPath.UPSTREAM_REVIEWS_FETCH`, where the reviews distribution ships it.
    """

    META_PACKAGE_METADATA = (
        SOURCE_TREE
        / WorkspaceLocation.PACKAGES
        / DIRECTORY.name
        / WorkspaceLocation.METADATA
    )
    """
    The ``basstler`` distribution's metadata in a checkout: its name, the interpreters
    it supports and where its version is read from.
    """


class RepositoryStateLocation(PathEnumeration):
    """
    Scratch state kept per repository, relative to its common git directory, which every
    worktree of the repository shares and no checkout or install of the package holds.
    """

    DIRECTORY = Path("basstler")
    """
    Everything this package keeps there.
    """

    PLAN_STATE_SYNC_STAMP = DIRECTORY / "plan-state-sync-sha"
    """
    The personal-notes commit this clone last read plan state at. The shell
    configuration's ``PLAN_STATE_SYNC_STAMP`` spells the same name.
    """

    PERSONAL_SETTINGS_SYNC_STAMP = DIRECTORY / "personal-settings-sync-hash"
    """
    The hash of the personal settings last synced into, or saved out of, this clone's
    local settings. The shell configuration's ``PERSONAL_SETTINGS_SYNC_STAMP`` spells
    the same name.
    """


class BasstlerVariable(EnvironmentVariable):
    """
    The environment variables this package's own shell configuration sets.
    """

    PLUGIN_ROOT = "BASSTLER_PLUGIN_ROOT"
    """
    The root of the Claude Code plugin whose hooks and skills run this package.
    """

    ENVIRONMENT_DIRECTORY = "BASSTLER_ENVIRONMENT_DIRECTORY"
    """
    The package's environment of the session's project, which every command of the
    session runs, whichever repository it runs in.
    """


class PluginFile(PathEnumeration):
    """
    Files of the plugin, relative to the plugin's root; each distribution names the ones
    it runs.
    """


class PluginLocation(PluginFile):
    """
    The plugin's files several distributions run, relative to the plugin's root.
    """

    HOOKS = Path("hooks")
    """
    The shell entry points that read and write personal-notes data.
    """

    PERSONAL_NOTES_CONFIGURATION_SCRIPT = HOOKS / "resolve-personal-notes-config.sh"
    """
    The shell configuration that resolves the personal-notes remote and branch, and
    fetches it.
    """

    PERSONAL_NOTES_WRITER_SCRIPT = HOOKS / "write-personal-notes-file.sh"
    """
    The helper that commits one file to the personal-notes branch and pushes it.
    """

    PERSONAL_NOTES_BRANCH_CREATION_SCRIPT = HOOKS / "create-personal-notes-branch.sh"
    """
    The helper that creates the personal-notes branch where it does not exist yet.
    """

    HOOK_REGISTRATIONS = HOOKS / "hooks.json"
    """
    The hooks the plugin registers with Claude Code, generated from the playbook.
    """

    ENTRY_POINT_SCRIPT = HOOKS / "basstler.sh"
    """
    Runs one module of the package once the package is ready to run, saying in one
    line why when it cannot be.
    """

    SESSION_START_SCRIPT = HOOKS / "session-start.sh"
    """
    The session-start hook: sets up the package's environment and loads the personal
    notes.
    """

    SESSION_START_MESSAGES_SCRIPT = HOOKS / "session-start-messages.sh"
    """
    The messages the session-start hook prints, sourced by it.
    """

    SESSION_RULES = HOOKS / "session-rules.md"
    """
    The rules every session using basstler's skills follows, which the session-start
    hook loads into the project's local instructions.
    """

    PERSONAL_NOTES_SAVING_SCRIPT = HOOKS / "save-personal-notes.sh"
    """
    Saves the personal notes in the project's local instructions back to the
    personal-notes branch.
    """

    PULL_REQUEST_PROGRESS_SAVING_SCRIPT = HOOKS / "save-pr-progress.sh"
    """
    Saves a branch's pull-request progress notes to the personal-notes branch.
    """

    PLAN_UPDATES_SINCE_SCRIPT = HOOKS / "plan-updates-since.sh"
    """
    Reports what changed in the plans since this clone last read them.
    """

    PERSONAL_SETTINGS_SAVING_SCRIPT = HOOKS / "save-personal-settings.sh"
    """
    Saves the user's personal settings to the personal-notes branch.
    """

    @property
    def path_under_exported_root(self) -> str:
        """
        This file as bash spells it under :attr:`BasstlerVariable.PLUGIN_ROOT`, for a
        message that names it without knowing the root.
        """
        return f"${BasstlerVariable.PLUGIN_ROOT}/{self}"


class BasstlerRepositoryLocation(PathEnumeration):
    """
    The directories of basstler's own repository a release reads, relative to its root.
    """

    PLUGIN = Path("plugin")
    """
    The Claude Code plugin.
    """


class PluginSkillLocation(PluginFile):
    """
    The files of the plugin's skills this package reads, relative to the plugin's root.
    """

    SKILLS = Path("skills")
    """
    The directory holding one directory per skill.
    """


class InstructionsTemplate(PathEnumeration):
    """
    The templates the agent instruction files are rendered from.
    """

    SKILL = INSTALLED_PACKAGE.shipped(ShippedPath.TEMPLATES / "skill.md.jinja")
    """
    The content of a skill's ``SKILL.md``: its frontmatter and title above its body.
    """


class SkillLocation(PathEnumeration):
    """
    The files every skill carries, relative to the skill's own directory.
    """

    INSTRUCTIONS = Path("SKILL.md")
    """
    The instructions Claude Code loads the skill from.
    """


class ProjectLocation(PathEnumeration):
    """
    The files this package reads, runs or writes in a project, relative to its root.

    Those on the personal-notes branch are relative to that branch's root, which is the
    same tree.
    """

    CLAUDE_CODE_DIRECTORY = Path(".claude")
    """
    The directory Claude Code reads a project's settings from.
    """

    PERSONAL_NOTES = CLAUDE_CODE_DIRECTORY / "personal"
    """
    Where the personal-notes branch keeps everything it holds.
    """

    PROJECT_STACK_CONFIGURATION = CLAUDE_CODE_DIRECTORY / "basstler" / "stack.toml"
    """
    The stack settings a project commits, naming its own upstream - layered over
    :attr:`PackageLocation.STACK_CONFIGURATION`.
    """

    PERSONAL_NOTES_DOCUMENT = PERSONAL_NOTES / "notes.md"
    """
    The notes file itself, unless a clone's settings put it elsewhere.
    """

    PLANS = PERSONAL_NOTES / "plans"
    """
    Where plans live on the personal-notes branch.

    Mirrors ``PLANS_DIR`` in ``resolve-personal-notes-config.sh``, which is the shell
    half of the same tooling; a test holds the two equal so the mirror cannot drift.
    """

    PLAN_RULES = PLANS / "_rules.yaml"
    """
    The rules every plan of the repository follows, one entry per rule.
    """

    PERSONAL_STACK_CONFIGURATION = PERSONAL_NOTES / "stack.toml"
    """
    The per-user override of :attr:`PROJECT_STACK_CONFIGURATION`.
    """

    PLAYBOOK = Path("basstler_playbook.py")
    """
    The module declaring the project's own playbook, where it has one.
    """

    PLAN_BRANCH_INDEX = PLANS / "_generated" / "branch-index.tsv"
    """
    The generated index naming the plan each item branch belongs to.

    Mirrors ``PLAN_BRANCH_INDEX_PATH`` in ``resolve-personal-notes-config.sh``.
    """

    GIT_IDENTITY = PERSONAL_NOTES / "git-identity"
    """
    The git identity of the notes repository's owner, which a clone with none of its own
    is given.

    Mirrors ``PERSONAL_GIT_IDENTITY_PATH`` in ``resolve-personal-notes-config.sh``.
    """


class WorkflowLocation(PathEnumeration):
    """
    The GitHub Actions workflows basstler runs or starts, relative to the root of the
    branch that holds each.
    """

    DIRECTORY = Path(".github") / "workflows"
    """
    Where GitHub reads a branch's workflows from.
    """

    MARK_VIEWED = DIRECTORY / "mark-viewed.yml"
    """
    The workflow on the user's repository that calls :attr:`~basstler.review_triage.locations.ReviewTriageWorkflowLocation.REVIEW_TRIAGE_MARK_VIEWED`
    with the user's own token.
    """

    PLAN_SITE = DIRECTORY / "plan-site.yml"
    """
    The workflow on the user's site repository that calls :attr:`~basstler.plan_site.locations.SiteWorkflowLocation.PLAN_SITE_BUILD`.
    """


class ClaudeCodeVariable(EnvironmentVariable):
    """
    The environment variables Claude Code sets for the commands it runs.
    """

    PROJECT_DIRECTORY = "CLAUDE_PROJECT_DIR"
    """
    The root of the project the session runs in.
    """

    PLUGIN_ROOT = "CLAUDE_PLUGIN_ROOT"
    """
    The plugin's installation directory, which Claude Code also substitutes into a
    plugin skill's own instructions when it loads them.
    """

    REMOTE = "CLAUDE_CODE_REMOTE"
    """
    :attr:`~basstler.environment.EnvironmentFlag.TRUE` in a Claude Code cloud session, whose proxy answers GitHub's REST API but
    not its GraphQL API.
    """

    SESSION_IDENTIFIER = "CLAUDE_CODE_SESSION_ID"
    """
    The session's own identifier, which names its transcript file.
    """

    CONFIGURATION_DIRECTORY = "CLAUDE_CONFIG_DIR"
    """
    Where Claude Code keeps its state, transcripts included, when not ``~/.claude``.
    """

    GIT_BASH_PATH = "CLAUDE_CODE_GIT_BASH_PATH"
    """
    The bash Claude Code runs its commands in on Windows, when set.
    """
