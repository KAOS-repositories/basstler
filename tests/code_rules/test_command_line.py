"""
Tests for the ``basstler code-rules`` commands.
"""

from __future__ import annotations

import pytest

from basstler.code_rules.command_line import (
    CodeRulesExitCode,
    check,
    fix,
    generate_agents_instructions,
    report_new_crossings,
)
from basstler.code_rules.instructions import AgentsInstructions
from basstler.code_rules.locale_encoding import LocaleEncodingChecker

from ..constants.paths import DocstringSnippet, ProseSnippet
from .fix_example import FixExample

# %% checking


def test_checking_fails_when_code_breaks_a_rule():
    """
    An overlong comment block breaks a checked rule.
    """
    assert check([ProseSnippet.COMMENT_BLOCKS], all_lines=True) == (
        CodeRulesExitCode.CHANGES_NEEDED
    )


def test_checking_passes_when_nothing_breaks_a_rule():
    """
    A documented module with short docstrings breaks no checked rule.
    """
    assert check([DocstringSnippet.DOCUMENTED_MODULE], all_lines=True) == (
        CodeRulesExitCode.SUCCESS
    )


# %% fixing


@pytest.fixture
def example() -> FixExample:
    """
    :return: The first example of the fix to text read and written as UTF-8.
    """
    return FixExample.all_of(LocaleEncodingChecker())[0]


def test_fixing_rewrites_a_file_breaking_a_rule_as_its_fix_does(example, tmp_path):
    """
    A file breaking a rule with a fix is rewritten as the fixed code, and the command
    reports the change.
    """
    source = tmp_path / example.before.name
    source.write_text(example.before.read_text(encoding="utf-8"), encoding="utf-8")

    assert fix([source]) == CodeRulesExitCode.CHANGES_NEEDED
    assert source.read_text(encoding="utf-8") == example.after.read_text(
        encoding="utf-8"
    )


def test_fixing_a_file_breaking_no_rule_writes_nothing(example, tmp_path):
    """
    A file that is already fixed is left as it is.
    """
    source = tmp_path / example.after.name
    source.write_text(example.after.read_text(encoding="utf-8"), encoding="utf-8")

    assert fix([source]) == CodeRulesExitCode.SUCCESS
    assert source.read_text(encoding="utf-8") == example.after.read_text(
        encoding="utf-8"
    )


# %% boundary crossings


def test_a_package_compared_with_its_own_commit_has_no_new_crossing():
    """
    Against the commit checked out, the base holds every crossing the package has.
    """
    assert report_new_crossings("HEAD") == CodeRulesExitCode.SUCCESS


# %% generating AGENTS.md


@pytest.fixture
def instructions(tmp_path, monkeypatch) -> AgentsInstructions:
    """
    :return: The ``AGENTS.md`` of an empty directory, made the working directory.
    """
    monkeypatch.chdir(tmp_path)
    return AgentsInstructions.of_repository(tmp_path)


def test_generating_writes_a_missing_file(instructions):
    """
    A missing ``AGENTS.md`` is written, and the command reports the change.
    """
    assert generate_agents_instructions() == CodeRulesExitCode.CHANGES_NEEDED
    assert instructions.is_current()


def test_generating_a_current_file_changes_nothing(instructions):
    """
    A current ``AGENTS.md`` is left as it is.
    """
    instructions.write()

    assert generate_agents_instructions() == CodeRulesExitCode.SUCCESS


def test_verifying_a_stale_file_fails_without_writing_it(instructions):
    """
    Verifying reports a stale ``AGENTS.md`` and leaves it stale.
    """
    instructions.path.write_text("stale", encoding="utf-8")

    assert generate_agents_instructions(verify=True) == (
        CodeRulesExitCode.CHANGES_NEEDED
    )
    assert not instructions.is_current()
