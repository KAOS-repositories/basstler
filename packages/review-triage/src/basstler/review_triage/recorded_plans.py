"""
The code modification plans a commit can record having applied, and reading which ones a
pull request's commits record.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Self

from basstler.class_property import classproperty
from basstler.code_modification.actions import PlanBuilder
from basstler.code_modification.source_tree import SourceTree
from basstler.git.commit_range import CommitRange
from basstler.review_triage.exceptions import UnknownRecordedPlanError
from basstler.review_triage.workspace_packages import NAMESPACE, WorkspacePackagesPlan

PLAN_TRAILER = "Code-Modification-Plan"
"""
The trailer of a commit message naming a plan the commit applied.
"""

# %% the plans


class RecordedPlan(StrEnum):
    """
    A code modification plan the triage rebuilds on a pull request's base and replays,
    by the name a commit records it under.
    """

    builder: PlanBuilder[SourceTree]
    """
    Builds the plan for the tree it is replayed on.
    """

    def __new__(cls, name: str, builder: PlanBuilder[SourceTree]) -> Self:
        """
        :param name: The name a commit records the plan under, the member's value.
        :param builder: Builds the plan.
        """
        member = str.__new__(cls, name)
        member._value_ = name
        member.builder = builder
        return member

    WORKSPACE_PACKAGES = "workspace-packages", WorkspacePackagesPlan()
    """
    Splits the single package into a directory per distribution.
    """

    @classmethod
    def named(cls, name: str) -> RecordedPlan:
        """
        :param name: A plan's name.
        :return: The plan of that name.
        :raises UnknownRecordedPlanError: If no plan has that name.
        """
        if name not in cls._value2member_map_:
            raise UnknownRecordedPlanError(name, tuple(cls))
        return cls(name)


# %% the records


@dataclass(frozen=True)
class PlanRecord:
    """
    A commit's record of a plan it applied.
    """

    commit: str
    """
    The commit, by any name git resolves.
    """

    plan: RecordedPlan
    """
    The plan it applied.
    """

    release: str | None = None
    """
    The version of basstler that applied the plan, ``None`` when the record does not
    say.
    """

    @classproperty
    def release_prefix(cls) -> str:
        """
        What precedes the release in a trailer, as a requirement on basstler.
        """
        return f"{NAMESPACE}=="

    @classproperty
    def separator(cls) -> str:
        """
        What separates the commit from the plan's name in an argument.
        """
        return "="

    @classmethod
    def from_argument(cls, argument: str) -> PlanRecord:
        """
        :param argument: A record as ``commit=plan``.
        :return: The record the argument makes.
        :raises ValueError: If the argument lacks the separator.
        :raises UnknownRecordedPlanError: If it names no known plan.
        """
        commit, name = argument.split(cls.separator, 1)
        return cls(commit, RecordedPlan.named(name))

    @classmethod
    def recorded_in(cls, commits: CommitRange) -> tuple[PlanRecord, ...]:
        """
        :param commits: A range of commits.
        :return: The plans the messages of its commits name in :data:`PLAN_TRAILER`,
            each as its name and optionally the release that applied it, newest commit
            first.
        :raises UnknownRecordedPlanError: If a trailer names no known plan.
        """
        listing = commits.git.run(
            "log",
            f"--format=%H%x1f%(trailers:key={PLAN_TRAILER},valueonly,separator=%x1f)",
            f"{commits.base_commit}..{commits.head_commit}",
        )
        return tuple(
            cls.from_trailer(commit, value)
            for commit, *values in (line.split("\x1f") for line in listing.splitlines())
            for value in values
            if value.strip()
        )

    @classmethod
    def from_trailer(cls, commit: str, value: str) -> PlanRecord:
        """
        :param commit: The commit whose message holds the trailer.
        :param value: The trailer's value: a plan's name, then optionally
            :attr:`release_prefix` and the release.
        :return: The record the trailer makes.
        :raises UnknownRecordedPlanError: If it names no known plan.
        """
        name, *requirement = value.split()
        release = next(
            (
                word.removeprefix(cls.release_prefix)
                for word in requirement
                if word.startswith(cls.release_prefix)
            ),
            None,
        )
        return cls(commit, RecordedPlan.named(name), release)
