"""
Tests for :mod:`basstler.plan_site.merge_workflow_refresh`: the command that brings an
out of date merge workflow up to date.
"""

from __future__ import annotations

import pytest

from basstler.exit_codes import StackExitCode
from basstler.locations import ClaudeCodeVariable
from basstler.plan_site.merge_workflow_refresh import refresh_merge_workflow

from basstler_testing.maintenance.fork import ForkCheckout

# %% a repository no plan site lists


def test_a_repository_no_plan_site_lists_is_left_alone(
    fork_checkout: ForkCheckout,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    """
    Without a recorded site there is no merge workflow to compare with, and the
    repository's own is none of the command's business.
    """
    monkeypatch.chdir(fork_checkout.project_root)
    monkeypatch.delenv(ClaudeCodeVariable.PROJECT_DIRECTORY, raising=False)

    exit_code = refresh_merge_workflow()

    assert (exit_code, capsys.readouterr().out) == (StackExitCode.SUCCESS, "")
