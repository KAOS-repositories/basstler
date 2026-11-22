"""
A goal whose targets live in the plans of another repository's notes.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from basstler.git.commands import GitCommandRunner
from basstler.github.repository import Repository
from basstler.locations import ProjectLocation
from basstler.plan.dependencies import (
    DependencyReference,
    PlanDirectory,
    ResolvedDependency,
)
from basstler.plan.goal import Goal
from basstler.plan.goal_path import NeededItems
from basstler.plan.model import ManifestKey, PlanDocument
from basstler.plan.other_repository_plans import OtherRepositoryPlans
from basstler_testing.manifest_builders import manifest_item, minimal_plan

HOME = "team/home-notes"
"""
The repository whose notes hold the goal.
"""

OTHER = "team/other-notes"
"""
The repository whose notes hold the plan the goal's target is in.
"""

NOTES_BRANCH = "claude/personal-notes"
"""
The branch both repositories keep their notes on.
"""


def write_plan(directory: Path, plan_id: str, items: list[dict]) -> None:
    """
    :param directory: A plans directory.
    :param plan_id: The plan to write into it.
    :param items: The plan's items.
    """
    manifest = directory / plan_id / PlanDocument.MANIFEST
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        yaml.safe_dump(
            minimal_plan(
                **{ManifestKey.IDENTIFIER.key: plan_id, ManifestKey.ITEMS.key: items}
            )
        ),
        encoding="utf-8",
    )


@pytest.fixture
def other_plans(tmp_path: Path) -> PlanDirectory:
    """
    :return: The other repository's plans: ``kpi/report`` waits for ``kpi/layout``.
    """
    directory = tmp_path / "other"
    write_plan(
        directory,
        "kpi",
        [
            manifest_item("layout", branch=None),
            manifest_item("report", branch=None, depends_on=["layout"]),
        ],
    )
    return PlanDirectory(directory, repository=OTHER)


@pytest.fixture
def home_plans(tmp_path: Path, other_plans: PlanDirectory) -> PlanDirectory:
    """
    :return: The goal's own plans: ``pilot/migrate`` waits for the other repository's
        ``kpi/report``, and the other repository's plans are known to them.
    """
    directory = tmp_path / "home"
    write_plan(
        directory,
        "pilot",
        [manifest_item("migrate", branch=None, depends_on=[f"{OTHER}:kpi/report"])],
    )
    return PlanDirectory(
        directory, repository=HOME, other_repositories={OTHER: other_plans}
    )


def goal_of(*targets: str) -> Goal:
    """
    :param targets: The goal's targets.
    :return: A goal over them.
    """
    return Goal(
        identifier="pilot-done", title="The pilot is done", targets=list(targets)
    )


class TestReferencingAnotherRepository:
    """
    A reference may name the repository whose notes hold the plan.
    """

    def test_the_repository_is_read_before_the_plan(self):
        reference = DependencyReference.from_text(f"{OTHER}:kpi/report")

        assert reference == DependencyReference("report", "kpi", OTHER)
        assert reference.text == f"{OTHER}:kpi/report"
        assert reference.is_well_formed
        assert reference.names_another_repository

    def test_a_reference_without_a_repository_reads_as_before(self):
        reference = DependencyReference.from_text("kpi/report")

        assert reference == DependencyReference("report", "kpi")
        assert not reference.names_another_repository

    @pytest.mark.parametrize(
        "text",
        ["team:kpi/report", f"{OTHER}:report", "a/b/c:kpi/report", ":kpi/report"],
    )
    def test_a_repository_is_owner_and_name_and_needs_a_plan(self, text: str):
        assert not DependencyReference.from_text(text).is_well_formed

    def test_a_goal_takes_a_target_in_another_repository(self):
        assert goal_of(f"{OTHER}:kpi/report").targets == [f"{OTHER}:kpi/report"]

    def test_a_goal_refuses_a_malformed_repository(self):
        with pytest.raises(ValueError):
            goal_of("team:kpi/report")


class TestTheItemsAGoalNeeds:
    """
    The goal's items and their dependencies are read from the notes that hold each.
    """

    def test_a_target_in_another_repository_resolves_there(
        self, home_plans: PlanDirectory
    ):
        needed = NeededItems.of_goal(goal_of(f"{OTHER}:kpi/report"), home_plans)

        assert not needed.unresolved
        assert set(needed.resolved_by_reference) == {
            DependencyReference("report", "kpi", OTHER),
            DependencyReference("layout", "kpi", OTHER),
        }

    def test_a_dependency_of_a_home_item_reaches_into_the_other_repository(
        self, home_plans: PlanDirectory
    ):
        needed = NeededItems.of_goal(goal_of("pilot/migrate"), home_plans)

        assert [reference.text for reference in needed.in_dependency_order()] == [
            f"{OTHER}:kpi/layout",
            f"{OTHER}:kpi/report",
            "pilot/migrate",
        ]

    def test_naming_the_home_repository_is_naming_no_repository(
        self, home_plans: PlanDirectory
    ):
        needed = NeededItems.of_goal(goal_of(f"{HOME}:pilot/migrate"), home_plans)

        assert DependencyReference("migrate", "pilot") in needed.resolved_by_reference

    def test_a_repository_whose_notes_cannot_be_read_leaves_the_target_unresolved(
        self, home_plans: PlanDirectory
    ):
        needed = NeededItems.of_goal(goal_of("team/unknown:kpi/report"), home_plans)

        assert [problem.reference_text for problem in needed.unresolved] == [
            "team/unknown:kpi/report"
        ]

    def test_another_repository_is_read_the_first_time_a_target_names_it(
        self, tmp_path: Path, other_plans: PlanDirectory
    ):
        reads: list[str] = []

        def read(repository: str) -> PlanDirectory:
            reads.append(repository)
            return other_plans

        home = PlanDirectory(tmp_path / "empty", read_other_repository=read)
        resolved = home.resolve(DependencyReference.from_text(f"{OTHER}:kpi/layout"))
        home.resolve(DependencyReference.from_text(f"{OTHER}:kpi/report"))

        assert isinstance(resolved, ResolvedDependency)
        assert reads == [OTHER]


class TestFetchingAnotherRepositorysPlans:
    """
    The goal command reads another repository's plans from its notes branch.
    """

    def publish(self, remote_root: Path, repository: str, plan: dict) -> None:
        """
        :param remote_root: The directory standing in for GitHub.
        :param repository: The repository to create there, as ``owner/name``.
        :param plan: The one plan its notes branch holds.
        """
        work = remote_root / "work"
        work.mkdir(parents=True)
        git = GitCommandRunner(work)
        git.run("init", "--quiet", "--initial-branch", NOTES_BRANCH)
        manifest = (
            work / ProjectLocation.PLANS / plan[ManifestKey.IDENTIFIER.key]
        ) / PlanDocument.MANIFEST
        manifest.parent.mkdir(parents=True)
        manifest.write_text(yaml.safe_dump(plan), encoding="utf-8")
        git.run("add", "--all")
        git.run("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "plans")
        bare = Path(Repository.parse(repository).clone_url_under(str(remote_root)))
        bare.parent.mkdir(parents=True)
        GitCommandRunner(remote_root).run(
            "clone", "--quiet", "--bare", str(work), str(bare)
        )

    def test_the_plans_on_its_notes_branch_are_read(self, tmp_path: Path):
        self.publish(
            tmp_path / "remotes",
            OTHER,
            minimal_plan(**{ManifestKey.IDENTIFIER.key: "kpi"}),
        )
        plans = OtherRepositoryPlans(
            tmp_path / "scratch", NOTES_BRANCH, str(tmp_path / "remotes")
        ).read(OTHER)

        assert plans is not None
        assert plans.repository == OTHER
        assert plans.plan("kpi") is not None

    def test_a_repository_without_the_notes_branch_reads_as_none(self, tmp_path: Path):
        (tmp_path / "remotes").mkdir()
        plans = OtherRepositoryPlans(
            tmp_path / "scratch", NOTES_BRANCH, str(tmp_path / "remotes")
        ).read(OTHER)

        assert plans is None
