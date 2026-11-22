"""
The Actions budget basstler holds every workflow in ``.github/workflows`` to.

Edit this file by hand from here on.
"""

from __future__ import annotations

from basstler.github.actions_budget import ActionsBudget, WorkflowLimits

# %% the budget


def actions_budget() -> ActionsBudget:
    """
    :return: This repository's Actions budget.
    """
    return ActionsBudget(
        overrides={
            # The Windows shards it calls run only for a push to main, yet are counted
            # on every pull-request push.
            "tests.yml": WorkflowLimits(jobs_per_push_run=8),
        },
    )
