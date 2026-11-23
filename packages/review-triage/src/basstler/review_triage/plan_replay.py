"""
Proving a file's change mechanical by replaying, on the pull request's base, the code
modification plans its commits record.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path

from basstler.code_modification.source_tree import SourceTree
from basstler.git.commands import GIT_TEXT_ENCODING
from basstler.git.commit_range import CommitRange, FileVersions
from basstler.review_triage.comparison import (
    ChangeKind,
    ChangeKinds,
    FileTriager,
    JudgmentContext,
)
from basstler.review_triage.recorded_plans import PlanRecord, RecordedPlan

# %% what replaying a plan changes

ReplayedPlanChange = ChangeKind(
    "ReplayedPlanChange",
    [(plan.name, f"{plan} plan replayed") for plan in RecordedPlan],
    module=__name__,
)
"""
The change replaying each :class:`RecordedPlan` makes, a member named after the plan.
"""

# %% the replay


@dataclass(frozen=True)
class PlanReplay:
    """
    The tree a pull request's triaged changes start from, once the plans its commits
    record are replayed on it.
    """

    replayed: SourceTree = field(default_factory=lambda: SourceTree({}))
    """
    The base tree with every plan applied, oldest commit's first.
    """

    plans_by_path: Mapping[Path, frozenset[RecordedPlan]] = field(default_factory=dict)
    """
    The plans whose replay changed each file, by its path.
    """

    @classmethod
    def from_records(
        cls, records: tuple[PlanRecord, ...], commits: CommitRange
    ) -> PlanReplay:
        """
        :param records: Plans commits applied.
        :param commits: The triaged commits.
        :return: The replay of the plans of *records* whose commit is one of
            *commits*, empty when none is.
        """
        triaged = commits.git.run(
            "rev-list", "--reverse", f"{commits.base_commit}..{commits.head_commit}"
        ).splitlines()
        resolved = {
            record: commits.git.commit_or_none(f"{record.commit}^{{commit}}")
            for record in records
        }
        replayed_records = sorted(
            (record for record in records if resolved[record] in triaged),
            key=lambda record: triaged.index(resolved[record]),
        )
        if not replayed_records:
            return cls()
        tree = SourceTree.from_commit(commits.base_tree)
        plans_by_path: dict[Path, frozenset[RecordedPlan]] = {}
        for record in replayed_records:
            replayed = record.plan.builder.build(tree).apply(tree).result
            for path in changed_paths(tree, replayed):
                plans_by_path[path] = plans_by_path.get(path, frozenset()) | {
                    record.plan
                }
            tree = replayed
        return cls(tree, plans_by_path)

    def plans_changing(self, change: FileVersions) -> frozenset[RecordedPlan]:
        """
        :param change: A file the pull request changes.
        :return: The plans whose replay changed the file at its path or at the path it
            was moved from.
        """
        paths = [Path(change.path)]
        if change.previous_path is not None:
            paths.append(Path(change.previous_path))
        return frozenset().union(
            *(self.plans_by_path.get(path, frozenset()) for path in paths)
        )

    def replayed_version(self, change: FileVersions) -> FileVersions:
        """
        :param change: A text file a replayed plan changed.
        :return: The file's change from the replayed tree to the head, at its head path,
            both texts stripped as :meth:`GitCommandRunner.file_at` reads them.
        """
        content = self.replayed.files.get(Path(change.path))
        return replace(
            change,
            previous_path=None,
            base_text=None
            if content is None
            else content.decode(GIT_TEXT_ENCODING).strip(),
        )


def changed_paths(before: SourceTree, after: SourceTree) -> set[Path]:
    """
    :param before: A tree.
    :param after: That tree changed.
    :return: The files added, removed or changed.
    """
    return {
        path
        for path in before.files.keys() | after.files.keys()
        if before.files.get(path) != after.files.get(path)
    }


# %% judging against the replay


@dataclass(frozen=True)
class ReplayingFileTriager(FileTriager):
    """
    Judges a file a replayed plan changed against the replayed tree instead of the base.
    """

    replay: PlanReplay = field(default_factory=PlanReplay)
    """
    The plans the triaged commits record, replayed on their base.
    """

    def judged_changes(
        self, change: FileVersions, context: JudgmentContext
    ) -> ChangeKinds | None:
        """
        :meth:`FileTriager.judged_changes`, judging a text file a replayed plan changed
        against the replayed tree and naming the plan among its kinds.
        """
        plans = self.replay.plans_changing(change)
        if not plans or change.is_binary:
            return super().judged_changes(change, context)
        kinds = frozenset(ReplayedPlanChange[plan.name] for plan in plans)
        replayed = self.replay.replayed_version(change)
        if replayed.base_text is None and replayed.head_text is None:
            return kinds
        judged = super().judged_changes(replayed, context)
        return None if judged is None else judged | kinds
