"""
Tests for the route a maintenance pass reads the upstream's open pull requests by.
"""

from __future__ import annotations

import pytest

from basstler.locations import ClaudeCodeVariable
from basstler.stack.locations import StackStateLocation
from basstler.maintenance.commands import MaintenancePass
from basstler.maintenance.upstream_read_route import UpstreamReadRoute
from basstler.upstream_reviews.exceptions import ActionNotInstalled

from basstler_testing.fork_checkout import ForkCheckout
from basstler_testing.maintenance.fork import make_configuration

# %% reading through the fork's Action


def test_a_pass_reading_through_the_action_asks_the_fork_s_action_branch(
    fork_checkout: ForkCheckout,
):
    """
    A pass reading through the Action fails on a fork that has no Action branch.
    """
    maintenance = MaintenancePass(
        configuration=make_configuration(),
        git=fork_checkout.git,
        board=fork_checkout.project_root / StackStateLocation.BOARD.name,
        upstream_read=UpstreamReadRoute.ACTION,
    )

    with pytest.raises(ActionNotInstalled):
        maintenance.upstream_pull_requests()


# %% choosing the route


def test_a_cloud_session_reads_through_the_action(monkeypatch):
    """
    A cloud session reads the upstream through the fork's Action.
    """
    monkeypatch.setenv(ClaudeCodeVariable.REMOTE, "true")

    assert UpstreamReadRoute.for_this_session() is UpstreamReadRoute.ACTION


def test_anywhere_else_reads_directly(monkeypatch):
    """
    Outside a cloud session the upstream is read directly.
    """
    monkeypatch.delenv(ClaudeCodeVariable.REMOTE, raising=False)

    assert UpstreamReadRoute.for_this_session() is UpstreamReadRoute.DIRECT
