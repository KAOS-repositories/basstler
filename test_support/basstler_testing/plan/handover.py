"""
The plan handover the dataset holds, and the repositories its plans are on.
"""

from __future__ import annotations

from enum import StrEnum

import pytest

from basstler.github.repository import Repository
from basstler.plan.locations import PlanHandoverLocation
from basstler.plan.handover import HandoverPlan, PlanHandover
from basstler.plan.model import PlanDocument, PlanManifest

from ..constants.paths import DatasetLocation

# %% the dataset handover


class HandedOverPlan(StrEnum):
    """
    The ids of the plans :attr:`DatasetLocation.HANDOVER` holds.
    """

    UPSTREAM = "upstream-work"
    """
    The plan whose item the other plan depends on.
    """

    DOWNSTREAM = "downstream-work"
    """
    The plan depending on an item of :attr:`UPSTREAM`.
    """


UNRELATED_BRANCH = "unrelated-branch"
"""
The branch of :attr:`DatasetLocation.UNRELATED_PROGRESS_NOTE`, which no handed-over plan
tracks.
"""

RECEIVERS_FORK = Repository("receiver", "repo")
"""
The receiver's own fork, which the dataset's plans are not on.
"""


def plans_repository() -> Repository:
    """
    :return: The repository the dataset's plans are on.
    """
    return PlanManifest.from_file(
        DatasetLocation.HANDOVER
        / PlanHandoverLocation.PLANS
        / HandedOverPlan.UPSTREAM
        / PlanDocument.MANIFEST
    ).default_repository


@pytest.fixture
def dataset_handover() -> PlanHandover:
    """
    :return: The handover the dataset holds.
    """
    return PlanHandover.from_directory(DatasetLocation.HANDOVER.value)


def plan_named(handover: PlanHandover, identifier: str) -> HandoverPlan:
    """
    :param handover: A handover.
    :param identifier: The id of one of its plans.
    :return: That plan.
    """
    return next(plan for plan in handover.plans if plan.identifier == identifier)
