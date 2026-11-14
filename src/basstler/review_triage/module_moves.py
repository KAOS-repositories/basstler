"""
Finding the modules a pull request moves, as renames of their dotted paths.
"""

from __future__ import annotations

from basstler.class_property import classproperty
from basstler.review_triage.commit_tree import MODULE_SUFFIX, CommitModules
from basstler.github.pull_request_changes import PullRequestChanges
from basstler.review_triage.rename_sources import RenameSource
from basstler.review_triage.renames import (
    DOTTED_NAME_SEPARATOR,
    Rename,
    RenameDecisions,
)

# %% detection


class ModuleMoveDetection(RenameSource):
    """
    Detects a moved module file as a rename of its dotted path, where the old path is
    gone from the head commit and the new one absent from the base commit.
    """

    @classproperty
    def label(cls) -> str:
        return "file move"

    def decisions(self, changes: PullRequestChanges) -> RenameDecisions:
        base = CommitModules(changes.commits.base_tree)
        head = CommitModules(changes.commits.head_tree)
        renames: list[Rename] = []
        for change in changes.files:
            if change.previous_path is None or {
                change.previous_path.suffix,
                change.path.suffix,
            } != {MODULE_SUFFIX}:
                continue
            old = base.module_path(change.previous_path)
            new = head.module_path(change.path)
            if (
                old != new
                and DOTTED_NAME_SEPARATOR in old
                and not head.tree.mentions(old)
                and not base.tree.mentions(new)
            ):
                renames.append(Rename(old, new, self))
        return RenameDecisions(tuple(sorted(renames, key=lambda rename: rename.old)))
