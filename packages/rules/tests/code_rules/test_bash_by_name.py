"""
Tests for :mod:`basstler.code_rules.bash_by_name`: reporting commands that start bash by
its name, which Windows resolves to WSL's launcher instead of Git Bash.
"""

from __future__ import annotations

from pathlib import Path


from basstler.code_modification.positions import PositionedModule
from basstler.code_modification.source_file import EditablePythonSourceFile
from basstler.code_rules.bash_by_name import BashByNameChecker, BashEnvironment
from basstler.code_rules.checker import CodeRulesCheck

from basstler_testing.constants.paths import (
    BashByNameSnippet,
    RuleFixExample,
    RuleFixExampleFile,
)

from .marked_snippet import MarkedSnippet

# %% commands


def test_a_subprocess_call_running_bash_by_its_name_is_reported():
    """
    A command line handed to :mod:`subprocess` is reported.
    """
    snippet = MarkedSnippet(BashByNameSnippet.SUBPROCESS_CALL)
    assert snippet.reported_lines(BashByNameChecker()) == snippet.marked_lines


def test_a_subprocess_imported_under_another_name_is_resolved():
    """
    A call is a :mod:`subprocess` call by what it imports, not by how it is spelled.
    """
    snippet = MarkedSnippet(BashByNameSnippet.IMPORTED_SUBPROCESS)
    assert snippet.reported_lines(BashByNameChecker()) == snippet.marked_lines


def test_a_returned_command_running_bash_by_its_name_is_reported():
    """
    A command line returned for a caller to run is reported.
    """
    snippet = MarkedSnippet(BashByNameSnippet.RETURNED_COMMAND)
    assert snippet.reported_lines(BashByNameChecker()) == snippet.marked_lines


def test_the_located_bash_and_a_tuple_of_names_are_not_reported():
    """
    The located bash is not, and neither is a tuple of names that runs nothing.
    """
    snippet = MarkedSnippet(BashByNameSnippet.LOCATED_BASH)
    assert snippet.reported_lines(BashByNameChecker()) == snippet.marked_lines


# %% the environment bash is located in


def located_environments(path: Path) -> list[BashEnvironment]:
    """
    :return: The environment the fix locates bash in, for each command line in *path*.
    """
    module = PositionedModule(EditablePythonSourceFile(path).parse())
    return [
        command.environment
        for command in BashByNameChecker().specifications_of_module(module)
    ]


def test_a_command_with_no_environment_in_scope_locates_bash_in_the_process():
    """
    Outside a function with an environment parameter, bash is located in the process's
    environment.
    """
    assert located_environments(BashByNameSnippet.SUBPROCESS_CALL) == [
        BashEnvironment.PROCESS_ENVIRONMENT
    ]


def test_a_command_with_an_environment_parameter_locates_bash_in_it():
    """
    In a function with an environment parameter, bash is located in that environment.
    """
    example = RuleFixExample.DIRECTORY / BashByNameChecker.__name__ / "subprocess-call"
    assert located_environments(example / RuleFixExampleFile.BEFORE) == [
        BashEnvironment.ENVIRONMENT_PARAMETER
    ]


# %% this repository


def test_no_code_in_the_repository_starts_bash_by_its_name(repository_sources):
    """
    Every bash the package, its scripts and its suite start is the one
    :class:`basstler.bash.Bash` locates, so the suite passes on Windows too.
    """
    violations = CodeRulesCheck((BashByNameChecker(),)).violations(repository_sources)
    assert [violation.render() for violation in violations] == []
