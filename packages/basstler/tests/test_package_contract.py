"""
The contract :mod:`basstler` has to keep: every caller importing the checkout's own source,
every module importable on its own, every entry point reachable through
``python3 -m``, every workflow that runs a module installing its dependencies first, one
version for the package and the plugin, and no Python in the plugin.

:mod:`basstler.package_layout` discovers the modules and the entry points from the package
itself, so nothing here is a second list of them, and the workflows are read from the
directory holding them rather than named.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import pytest

from basstler.github.basstler_project import BasstlerWorkflowInput
from basstler.bash import Bash
from basstler.class_property import classproperty
from basstler.document_references import PACKAGE_NAME
from basstler.environment import GitBashVariable
from basstler.package_map import Workspace
from basstler.locations import (
    ClaudeCodeVariable,
    PackageLocation,
    PluginLocation,
    WorkflowLocation,
)
from basstler.plan.locations import PlanProjectLocation
from basstler.plan_site.locations import SiteProjectLocation
from basstler.package_layout import (
    PackageModule,
    command_line_entry_points,
    package_modules,
)
from basstler.regular_expression import (
    Anchor,
    CharacterClass,
    CharacterRange,
    CharacterSet,
    DoubleQuoted,
    RegularExpression,
    Separator,
    Wildcard,
)
from basstler.shell_configuration import PersonalNotesSetting
from basstler.shell_configuration import FetchedBranchReference

from basstler_testing.constants.environment import (
    ConfigurationVariable,
    SearchPathVariable,
)
from basstler_testing.constants.paths import DatasetLocation, RepositoryLocation
from basstler_testing.constants.patterns import DocumentGroup
from basstler_testing.plugin_manifest import PluginManifestKey
from basstler_testing.project_declaration import HatchVersionSource, ProjectDeclaration
from basstler_testing.scratch_repository import ScratchRepository
from basstler_testing.script_runner import ScriptRunner, configuration_value

WORKFLOWS_DIRECTORY = RepositoryLocation.WORKFLOWS
"""
Where this repository's Actions workflows live.

Read as a directory rather than named one by one, so a workflow added later is checked
without anyone recording that it exists.
"""


SHELL_CONFIGURATION = (
    RepositoryLocation.HOOKS / PluginLocation.PERSONAL_NOTES_CONFIGURATION_SCRIPT.name
)
"""
The file the bash callers source, which is where a module gets a shell name and the
interpreter its import path.
"""


@dataclass(frozen=True, kw_only=True)
class ConfiguredInterpreterRunner(ScriptRunner):
    """
    Runs this interpreter the way a bash caller does: after sourcing the shell
    configuration, and so with whatever import path it sets up.
    """

    @property
    def command(self) -> tuple[str, ...]:
        """:return: bash sourcing the configuration, then handing over to this interpreter."""
        return tuple(
            Bash.locate(os.environ).command(
                "-c",
                'source "$0" && exec "$@"',
                str(SHELL_CONFIGURATION),
                sys.executable,
            )
        )


def run_as_a_caller(*arguments: str) -> subprocess.CompletedProcess[str]:
    """
    Run this interpreter as a bash caller does, with an environment that cannot help it
    find the package.

    ``PYTHONPATH`` is removed so a pass proves the import path comes from the shell
    configuration, rather than from whatever the caller's shell happened to export.

    :param arguments: Arguments to the interpreter, e.g. ``("-c", "import basstler")``.
    :return: The completed process, with output captured as text.
    """
    return ConfiguredInterpreterRunner(
        project_root=RepositoryLocation.ROOT.value,
        removed_variable_prefixes=(SearchPathVariable.IMPORT_PATH,),
    ).run(*arguments)


class ContractGroup(StrEnum):
    """
    The parts the contract's patterns read back.
    """

    MODULE_PATH = "module_path"
    """
    The dotted path of a module of the package.
    """


class InstallCommand(StrEnum):
    """
    The commands that install a package and the dependencies its metadata declares.
    """

    PIP = "pip install"
    """
    pip's own install.
    """

    UV_PIP = "uv pip install"
    """
    uv's pip-compatible install.
    """

    UV_SYNC = "uv sync"
    """
    uv's install of a project's environment.
    """


class ContractPattern:
    """
    The patterns that read the shell configuration, the workflows and the skill documents.
    """

    @classproperty
    def module_variable(cls) -> re.Pattern[str]:
        """
        One assignment of a module's path in the shell configuration, as
        ``MODULE="basstler.plan_manifest_tools"``.
        """
        lowercase_name = CharacterSet.any_of(CharacterRange.ASCII_LOWERCASE_LETTER, "_")
        return RegularExpression.sequence(
            Anchor.LINE_START,
            CharacterSet.any_of(CharacterRange.ASCII_UPPERCASE_LETTER, "_")
            .one_or_more()
            .captured_as(DocumentGroup.VARIABLE),
            "=",
            DoubleQuoted(
                RegularExpression.sequence(
                    PACKAGE_NAME,
                    RegularExpression.sequence(
                        ".", lowercase_name.one_or_more()
                    ).one_or_more(),
                ).captured_as(ContractGroup.MODULE_PATH)
            ),
        ).compiled()

    @classproperty
    def dependency_install(cls) -> re.Pattern[str]:
        """
        A step that installs this package, and with it the dependencies its metadata
        declares, however the caller spells the directory, as ``uv sync --package``.
        """
        return RegularExpression.sequence(
            RegularExpression.either(*InstallCommand),
            Wildcard.ANY_CHARACTER_EXCEPT_LINE_BREAK.zero_or_more(),
            PACKAGE_NAME,
        ).compiled()

    @classproperty
    def workspace_sync(cls) -> re.Pattern[str]:
        """
        A step that installs this package from a clone of the workspace, as
        ``uv sync --package basstler``.
        """
        return RegularExpression.sequence(
            InstallCommand.UV_SYNC,
            Wildcard.ANY_CHARACTER_EXCEPT_LINE_BREAK.zero_or_more(),
            "--package",
            Separator.WHITESPACE,
            PACKAGE_NAME,
        ).compiled()

    @classproperty
    def basstler_reference(cls) -> re.Pattern[str]:
        """
        The ``@<branch or tag>`` the caller uses basstler's workflow at, or the
        ``basstler_branch_or_tag: <branch or tag>`` it installs the package at.
        """
        return RegularExpression.sequence(
            RegularExpression.either(
                f"{PACKAGE_NAME}/{WorkflowLocation.UPSTREAM_REVIEWS.as_posix()}@",
                f"{BasstlerWorkflowInput.BRANCH_OR_TAG}: ",
            ),
            CharacterClass.NON_WHITESPACE.one_or_more().captured_as(
                BasstlerWorkflowInput.BRANCH_OR_TAG
            ),
        ).compiled()

    @classproperty
    def shell_variable_reference(cls) -> re.Pattern[str]:
        """
        A ``${NAME}`` reference to an upper-case shell variable, as a skill document
        writes one.
        """
        return RegularExpression.sequence(
            "${",
            RegularExpression.sequence(
                CharacterRange.ASCII_UPPERCASE_LETTER,
                CharacterSet.any_of(
                    CharacterRange.ASCII_UPPERCASE_LETTER,
                    CharacterRange.ASCII_DIGIT,
                    "_",
                ).zero_or_more(),
            ).captured_as(DocumentGroup.VARIABLE),
            "}",
        ).compiled()


def invocation_of(module: PackageModule) -> re.Pattern[str]:
    """
    Every spelling a caller can invoke a module by: ``-m`` and its command path, or a
    shell variable the configuration assigns that path, so a mere mention such as a
    repository name does not count.

    :param module: The module to invoke.
    :return: A pattern matching any of those invocations.
    """
    assignments = ContractPattern.module_variable.findall(
        SHELL_CONFIGURATION.read_text(encoding="utf-8")
    )
    variables = [
        RegularExpression.sequence(
            "$",
            RegularExpression.literal("{").optional(),
            variable,
            Anchor.WORD_BOUNDARY,
        )
        for variable, path in assignments
        if path == module.command_path
    ]
    module_run = RegularExpression.sequence(
        "-m",
        Separator.WHITESPACE.one_or_more(),
        module.command_path,
        RegularExpression.negative_lookahead(
            CharacterSet.any_of(CharacterClass.WORD_CHARACTER, ".")
        ),
    )
    return RegularExpression.either(module_run, *variables).compiled()


def installs_the_dependencies(caller_source: str) -> bool:
    """
    :param caller_source: A caller's own file.
    :return: Whether it installs this package's dependencies before running anything.
    """
    return ContractPattern.dependency_install.search(caller_source) is not None


# %% a caller imports the checkout's own source


def test_a_caller_imports_the_checkouts_own_source_with_no_install():
    """
    What a bash caller of a plugin sitting in a checkout imports is every distribution's
    part of the package in that checkout, even where nothing is installed: ``-S`` leaves
    site-packages, and with it any install, out of the search.
    """
    result = run_as_a_caller(
        "-S", "-c", "import basstler; print(*basstler.__path__, sep='\\n')"
    )

    assert result.returncode == 0, result.stderr
    assert {Path(part) for part in result.stdout.splitlines()} == set(
        Workspace(PackageLocation.SOURCE_TREE.value).namespace_package.directories
    )


def test_the_build_reads_its_version_from_the_release_tag():
    """
    A release is only a tag on its merge commit, so the build reads the version from git
    rather than from a file a merge would then have to commit; a source with no history
    still builds.
    """
    version_source = HatchVersionSource.of_this_package()

    assert version_source.source == "vcs"
    assert version_source.fallback_version is not None


def test_the_plugin_manifest_names_no_version():
    """
    A version in the manifest would need a commit after each release, and would keep
    marketplace installs on it until it changed.
    """
    manifest = json.loads(
        RepositoryLocation.PLUGIN_MANIFEST.read_text(encoding="utf-8")
    )

    assert PluginManifestKey.VERSION not in manifest


# %% each module stands on its own


@pytest.mark.parametrize("module", package_modules(), ids=lambda module: module.name)
def test_every_module_imports_on_its_own(module: PackageModule):
    """
    Each module imports in an interpreter that has imported nothing else.

    One subprocess per module rather than one for all of them: an import cycle only bites
    whichever module a caller reaches first, so a suite that imports them together can
    stay green while a single-module entry point is broken.
    """
    result = run_as_a_caller("-c", f"import {module.import_path}")

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "module", command_line_entry_points(), ids=lambda module: module.name
)
def test_every_entry_point_answers_help_through_the_module_runner(
    module: PackageModule,
):
    """
    Each entry point is reachable through ``python -m`` and its command path.

    That form rather than a path to the file: a module run by path puts its own directory
    on ``sys.path`` instead of the repository root, so its absolute imports of its
    siblings would not resolve. Every bash caller invokes them this way.
    """
    result = run_as_a_caller("-m", module.command_path, "--help")

    assert result.returncode == 0, result.stderr


# %% what a workflow runs, and what it installs first


def workflows_that_run_a_module() -> tuple[tuple[Path, PackageModule], ...]:
    """
    Every Actions workflow that runs a module of this package, paired with that module.

    Discovered from the workflow directory and the package itself rather than declared:
    an Actions runner is the one caller no session hook reaches, so a workflow added
    later has to be found rather than remembered.

    :return: Each workflow's path and the module it runs, in path then name order.
    """
    return tuple(
        (workflow_path, module)
        for workflow_path in sorted(WORKFLOWS_DIRECTORY.glob("*.yml"))
        for module in package_modules()
        if invocation_of(module).search(workflow_path.read_text(encoding="utf-8"))
    )


def package_entry_point() -> PackageModule:
    """
    :return: The module ``python -m basstler`` runs, as the package's discovery finds it.
    """
    (entry_point,) = (
        module for module in package_modules() if module.name == "__main__"
    )
    return entry_point


def test_a_workflow_that_only_names_the_repository_runs_no_module():
    workflow_text = DatasetLocation.WORKFLOW_NAMING_THE_REPOSITORY.read_text(
        encoding="utf-8"
    )

    assert invocation_of(package_entry_point()).search(workflow_text) is None


def test_a_workflow_that_runs_the_entry_point_is_found():
    workflow_text = DatasetLocation.WORKFLOW_RUNNING_THE_PACKAGE.read_text(
        encoding="utf-8"
    )

    assert invocation_of(package_entry_point()).search(workflow_text) is not None


def test_every_workflow_that_runs_a_module_installs_the_dependencies_first():
    """
    A runner starts with nothing installed and no hook runs on it, so a workflow that
    invokes a module installs this package's dependencies itself.

    The emptiness assertion is the scan's own coverage: a discovery that finds no
    workflow checks nothing, and a parametrization over it would pass while doing so.
    """
    running = workflows_that_run_a_module()

    assert running != ()
    assert [
        workflow_path.name
        for workflow_path, _ in running
        if not installs_the_dependencies(workflow_path.read_text(encoding="utf-8"))
    ] == []


def test_every_workflow_that_installs_the_package_syncs_it_from_the_workspace():
    """
    The repository root is a virtual workspace with no package of its own, and the
    sibling distributions are pinned to versions only the lock resolves.
    """
    installing = [
        workflow_path
        for workflow_path in sorted(WORKFLOWS_DIRECTORY.glob("*.yml"))
        if ContractPattern.dependency_install.search(
            workflow_path.read_text(encoding="utf-8")
        )
    ]

    assert installing != []
    assert [
        workflow_path.name
        for workflow_path in installing
        if not ContractPattern.workspace_sync.search(
            workflow_path.read_text(encoding="utf-8")
        )
    ] == []


def test_the_windows_workflow_accepts_a_shard_holding_none_of_a_distributions_tests():
    """
    A distribution with few tests has none in some shard, which pytest reports with the
    status for no tests collected, not as a failure.
    """
    workflow_text = (WORKFLOWS_DIRECTORY / "windows-tests.yml").read_text(
        encoding="utf-8"
    )

    assert f"-ne {int(pytest.ExitCode.NO_TESTS_COLLECTED)}" in workflow_text


def test_the_example_caller_uses_one_branch_or_tag_throughout():
    """
    A project copies the example caller as it stands, so the workflow it uses and the
    package that workflow installs have to come from the same branch or tag.
    """
    caller = RepositoryLocation.ROOT / "docs" / "examples" / "upstream-reviews.yml"

    references = ContractPattern.basstler_reference.findall(
        caller.read_text(encoding="utf-8")
    )

    assert len(references) == 2
    assert len(set(references)) == 1


# %% nothing is left behind


def test_the_plugin_carries_no_python_module():
    """
    The plugin keeps its SKILL.md files, manifest and bash entry points - Claude Code
    discovers those by path - and not one Python file: every module is the package's,
    installed at the plugin's own version.
    """
    remaining_module_paths = sorted(
        str(path.relative_to(RepositoryLocation.ROOT.value))
        for path in RepositoryLocation.PLUGIN.value.rglob("*.py")
    )

    assert remaining_module_paths == []


def test_no_module_sits_directly_in_the_source_tree():
    """
    The package's modules live under ``src/``, and nothing beside ``pyproject.toml`` is
    one.

    A module a branch adds where the package used to be merges with no conflict and is
    then never imported, so the move's own completeness has to be asserted rather than
    trusted to the merge.
    """
    stray_module_paths = sorted(
        str(path.relative_to(RepositoryLocation.ROOT.value))
        for path in PackageLocation.SOURCE_TREE.value.glob("*.py")
    )

    assert stray_module_paths == []


# %% the shell's copies of what the package states


def test_the_shell_asks_for_the_interpreters_the_package_supports():
    """
    The interpreter an environment is created from satisfies the package's own
    ``requires-python``, so the two cannot disagree about which versions run it.
    """
    assert (
        configuration_value(ConfigurationVariable.PYTHON_REQUIREMENT)
        == ProjectDeclaration.of_this_package().requires_python
    )


def test_the_shell_fetches_the_notes_branch_where_the_package_reads_it():
    """
    The package reads the personal-notes branch at the ref the shell's fetch keeps it at.
    """
    assert (
        configuration_value(ConfigurationVariable.PERSONAL_NOTES_REFERENCE)
        == FetchedBranchReference.PERSONAL_NOTES
    )


def test_the_shell_keeps_progress_notes_where_the_package_reads_them():
    """
    :attr:`PlanProjectLocation.PULL_REQUEST_PROGRESS` mirrors ``PR_PROGRESS_DIRECTORY``.
    """
    assert (
        configuration_value(ConfigurationVariable.PULL_REQUEST_PROGRESS_DIRECTORY)
        == PlanProjectLocation.PULL_REQUEST_PROGRESS.as_posix()
    )


@pytest.mark.parametrize(
    "argument",
    [
        f"{FetchedBranchReference.PERSONAL_NOTES}:{SiteProjectLocation.PLAN_HUB.as_posix()}",
        f"+refs/heads/{PersonalNotesSetting.BRANCH.default}:"
        f"{FetchedBranchReference.PERSONAL_NOTES}",
    ],
)
def test_git_bash_passes_a_notes_branch_argument_to_git_as_written(
    argument: str, scratch_repository: ScratchRepository
):
    """
    Git Bash rewrites an argument holding ``:`` and ``/`` as a Windows path unless it
    starts with an excluded prefix, so the hooks' object names and fetch refspecs are
    excluded for every program they run.
    """
    exclusions = scratch_repository.configuration_output(
        f"printenv {GitBashVariable.ARGUMENT_CONVERSION_EXCLUSIONS}"
    )

    assert any(argument.startswith(prefix) for prefix in exclusions.strip().split(";"))


# %% what the skill documents name


def variables_the_configuration_defines() -> frozenset[str]:
    """
    :return: Every variable set once the shell configuration is sourced, in an environment
        carrying nothing but a search path, so an inherited variable cannot pass for one
        the configuration defines.
    """
    return frozenset(
        subprocess.run(
            Bash.locate(os.environ).command(
                "-c", 'source "$0" && compgen -v', SHELL_CONFIGURATION
            ),
            cwd=RepositoryLocation.ROOT.value,
            capture_output=True,
            encoding="utf-8",
            check=True,
            env={
                SearchPathVariable.EXECUTABLE_SEARCH_PATH: os.environ[
                    SearchPathVariable.EXECUTABLE_SEARCH_PATH
                ]
            },
        ).stdout.split()
    )


def test_every_variable_a_skill_document_names_is_defined():
    """
    A document naming a variable nothing defines hands its reader an empty string, and a
    command built from it fails far from the cause - a rename or a move leaves exactly
    this behind.
    """
    named = {
        variable_name
        for document in RepositoryLocation.PLUGIN.value.rglob("*.md")
        for variable_name in ContractPattern.shell_variable_reference.findall(
            document.read_text(encoding="utf-8")
        )
    }

    assert named != set()
    assert (
        sorted(named - variables_the_configuration_defines() - set(ClaudeCodeVariable))
        == []
    )
