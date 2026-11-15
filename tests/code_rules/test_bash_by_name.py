"""
Tests for :mod:`basstler.code_rules.bash_by_name`: reporting commands that start bash by
its name, which Windows resolves to WSL's launcher instead of Git Bash.
"""

from __future__ import annotations

from pathlib import Path

import libcst

from basstler.code_rules.bash_by_name import BashByNameChecker
from basstler.code_rules.checker import CodeRulesCheck
from basstler.code_rules.commands import CodeRulesCommand
from basstler.code_rules.fixes import SourceFixer

from ..constants.paths import BashByNameSnippet

# %% helpers


def violation_lines(path: Path) -> list[int]:
    """
    :return: The first line of each violation the checker reports in *path*.
    """
    return [violation.first_line for violation in BashByNameChecker().violations(path)]


# %% commands


def test_a_subprocess_call_running_bash_by_its_name_is_reported():
    """
    A command line handed to :mod:`subprocess` is reported.
    """
    assert violation_lines(BashByNameSnippet.SUBPROCESS_CALL) == [9]


def test_a_returned_command_running_bash_by_its_name_is_reported():
    """
    A command line returned for a caller to run is reported.
    """
    assert violation_lines(BashByNameSnippet.RETURNED_COMMAND) == [12]


def test_the_located_bash_and_a_tuple_of_names_are_not_reported():
    """
    The located bash is not, and neither is a tuple of names that runs nothing.
    """
    assert violation_lines(BashByNameSnippet.LOCATED_BASH) == []


# %% where no environment is in scope


def test_a_command_with_no_environment_in_scope_is_reported_without_a_fix():
    """
    The report says why the fix leaves the command.
    """
    violation = next(BashByNameChecker().violations(BashByNameSnippet.SUBPROCESS_CALL))
    assert violation.description.endswith(
        f"`{CodeRulesCommand.FIX.invocation}` leaves it"
    )


def test_the_fix_leaves_a_command_with_no_environment_in_scope_as_it_is():
    """
    Fixing changes nothing where there is no environment to locate bash in.
    """
    source = BashByNameSnippet.SUBPROCESS_CALL.read_text(encoding="utf-8")
    fixed = SourceFixer((BashByNameChecker(),)).fixed(libcst.parse_module(source))
    assert fixed.module.code == source


# %% this repository


def test_no_code_in_the_repository_starts_bash_by_its_name(repository_sources):
    """
    Every bash the package, its scripts and its suite start is the one
    :class:`basstler.bash.Bash` locates, so the suite passes on Windows too.
    """
    violations = CodeRulesCheck((BashByNameChecker(),)).violations(repository_sources)
    assert [violation.render() for violation in violations] == []
