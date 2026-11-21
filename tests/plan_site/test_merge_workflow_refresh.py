"""
Tests for :mod:`basstler.plan_site.merge_workflow_refresh`: the command that brings an
out of date merge workflow up to date.
"""

from __future__ import annotations

import pytest

from basstler.exit_codes import StackExitCode
from basstler.locations import ClaudeCodeVariable
from basstler.github.release_version import PublishedReleases, ReleaseVersion
from basstler.github.repository import Repository
from basstler.plan_site import merge_workflow_refresh
from basstler.plan_site.merge_workflow_refresh import refresh_merge_workflow
from basstler.plan_site.site_repository import SiteRepository

from ..maintenance.fork import ForkCheckout

ANY_RECORDED_SITE = SiteRepository(Repository("an-owner", "a-site"))
"""
A plan site this clone's notes record.
"""


def refuse_to_clone(*arguments: object) -> None:
    """
    Fail the test: the command went on to compare workflows.
    """
    pytest.fail("an older release must not go on to propose a workflow")


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


# %% an older release than the latest


def test_an_older_release_proposes_nothing_so_it_cannot_revert_a_newer_one(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """
    A session running a release behind the latest would generate the older workflow and
    propose it over the newer release's, which the next session reverts in turn.
    """
    monkeypatch.setattr(
        merge_workflow_refresh, "recorded_site", lambda: ANY_RECORDED_SITE
    )
    monkeypatch.setattr(ReleaseVersion, "installed", lambda: ReleaseVersion(1, 0, 0))
    monkeypatch.setattr(
        PublishedReleases, "latest", lambda self: ReleaseVersion(1, 0, 1)
    )
    monkeypatch.setattr(merge_workflow_refresh, "clone_publication", refuse_to_clone)

    exit_code = refresh_merge_workflow()

    assert (exit_code, capsys.readouterr().out) == (StackExitCode.SUCCESS, "")
