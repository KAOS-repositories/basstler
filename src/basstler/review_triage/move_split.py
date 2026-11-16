"""
A pull request's change split into a commit that only moves definitions, unchanged, and
one making every other change, so a reviewer reads only the second.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath

from basstler.git.commands import GitCommandRunner
from basstler.git.commit_range import CommitRange, FileVersions
from basstler.github.pull_request_changes import PullRequestChanges, RestPullRequest
from basstler.review_triage.definition_moves import DefinitionMoveDetection
from basstler.review_triage.exceptions import UnprovenMoveError
from basstler.review_triage.moved_definitions import MovedDefinition, MovedDefinitions
from basstler.review_triage.python_source import LineSpan, PythonSource
from basstler.review_triage.triage import PullRequestTriager

# %% the files of the move


@dataclass(frozen=True)
class MoveOnlyTree:
    """
    The files a pull request's definition moves change when nothing else changes: each
    moved definition cut from the module it left and pasted after the module it moved
    into, both in their base versions.
    """

    changes: PullRequestChanges
    """
    The pull request's whole change.
    """

    moved: MovedDefinitions
    """
    The definitions it moves.
    """

    @property
    def changed_files(self) -> dict[PurePosixPath, FileVersions]:
        """
        Each file the pull request changes, by its head path.
        """
        return {change.path: change for change in self.changes.files}

    def files(self) -> dict[str, str]:
        """
        :return: The text of each file the moves change, by path, without its final
            newline.
        """
        texts: dict[PurePosixPath, str] = {}
        for path in sorted({moved.source_path for moved in self.moved.definitions}):
            texts[path] = self.cut(path)
        for path in sorted({moved.target_path for moved in self.moved.definitions}):
            texts[path] = self.pasted(path, texts.get(path, self.base_text(path)))
        return {str(path): text.removesuffix("\n") for path, text in texts.items()}

    def base_text(self, path: PurePosixPath) -> str:
        """
        :param path: A file the pull request's head holds.
        :return: Its base version at the same path, empty when the base has none there.
        """
        change = self.changed_files.get(path)
        if change is None or change.previous_path is not None:
            return ""
        return change.base_text or ""

    def cut(self, path: PurePosixPath) -> str:
        """
        :param path: A module definitions move out of, in the base commit.
        :return: Its base version without them and the blank lines above each.
        """
        leaving = self.moved.leaving(path)
        lines = leaving[0].source_text.splitlines(keepends=True)
        spans = [self.span_with_blank_lines_above(moved, lines) for moved in leaving]
        removed = {
            number for span in spans for number in range(span.first, span.last + 1)
        }
        return "".join(
            line
            for number, line in enumerate(lines, start=1)
            if number not in removed
        )

    def pasted(self, path: PurePosixPath, start: str) -> str:
        """
        :param path: A module definitions move into, in the head commit.
        :param start: Its text before they arrive.
        :return: That text followed by each arriving definition's base version, in the
            order the head version holds them, two blank lines apart.
        """
        head = PythonSource(self.changed_files[path].head_text or "")
        arriving = sorted(
            self.moved.arriving_at(path),
            key=lambda moved: head.definition_span(moved.name).first,
        )
        blocks = [self.base_lines(moved) for moved in arriving]
        return "\n\n".join([start, *blocks] if start else blocks)

    @staticmethod
    def base_lines(moved: MovedDefinition) -> str:
        """
        :param moved: A moved definition.
        :return: Its lines in the module it left, exactly as they were.
        """
        lines = moved.source_text.splitlines(keepends=True)
        span = moved.source.definition_span(moved.name)
        return "".join(lines[span.first - 1 : span.last])

    @staticmethod
    def span_with_blank_lines_above(
        moved: MovedDefinition, lines: list[str]
    ) -> LineSpan:
        """
        :param moved: A moved definition.
        :param lines: The lines of the module it left.
        :return: Its lines there, with the blank lines right above it.
        """
        span = moved.source.definition_span(moved.name)
        first = span.first
        while first > 1 and not lines[first - 2].strip():
            first -= 1
        return LineSpan(first, span.last)


# %% the split


@dataclass(frozen=True)
class MoveSplit:
    """
    A pull request's change as two commits on its merge base: one moving definitions
    unchanged, then one making every other change and holding its head's tree.
    """

    pull_request: RestPullRequest
    """
    The pull request split.
    """

    move_commit: str
    """
    The commit moving its definitions unchanged.
    """

    remaining_commit: str
    """
    The commit making every other change, whose tree is the pull request's head tree.
    """

    def publish(self, git: GitCommandRunner, location: str) -> None:
        """
        Replace the pull request's branch with the split, refused when the branch has
        moved since the pull request was read.

        :param git: The checkout holding the split.
        :param location: The remote or URL of the repository holding the branch.
        """
        branch = f"refs/heads/{self.pull_request.head.branch}"
        git.run(
            "push",
            "--quiet",
            f"--force-with-lease={branch}:{self.pull_request.head.commit}",
            location,
            f"{self.remaining_commit}:{branch}",
        )


@dataclass(frozen=True)
class MoveSplitter:
    """
    Splits pull requests that move definitions, proving the move commit mechanical.
    """

    git: GitCommandRunner
    """
    The checkout holding the pull requests' commits.
    """

    triager: PullRequestTriager = field(default_factory=PullRequestTriager)
    """
    Finds the moved definitions and proves the move commit mechanical.
    """

    def split(self, changes: PullRequestChanges) -> MoveSplit | None:
        """
        :param changes: A pull request's whole change, from its merge base.
        :return: Its split, dated as its head commit so the same pull request always
            splits into the same commits; ``None`` when it moves no definition.
        :raises UnprovenMoveError: If the move commit changes a file the triage cannot
            prove mechanical.
        """
        moved = DefinitionMoveDetection().moved_definitions(
            changes, self.triager.renames(changes)
        )
        if not moved.definitions:
            return None
        base_commit = changes.commits.base_commit
        head_commit = changes.commits.head_commit
        date = self.git.run("show", "--no-patch", "--format=%cI", head_commit)
        move_commit = self.git.commit_files(
            base_commit,
            MoveOnlyTree(changes, moved).files(),
            "Move definitions unchanged\n\n"
            + "\n".join(f"- {each.old_path} -> {each.new_path}" for each in moved.definitions),
            date=date,
        )
        self.prove(changes, move_commit)
        remaining_commit = self.git.commit_tree(
            self.git.tree_of(head_commit),
            (move_commit,),
            f"Make the changes of #{changes.pull_request.number} beyond the moves\n\n"
            f"Its tree is that of the former head {head_commit}.",
            date,
        )
        return MoveSplit(changes.pull_request, move_commit, remaining_commit)

    def prove(self, changes: PullRequestChanges, move_commit: str) -> None:
        """
        :param changes: A pull request's whole change.
        :param move_commit: The commit moving its definitions, on its merge base.
        :raises UnprovenMoveError: If the triage leaves any file the commit changes for
            review.
        """
        move = CommitRange(self.git, changes.commits.base_commit, move_commit)
        outcome = self.triager.triage(
            PullRequestChanges(
                changes.pull_request, move, move.file_versions(), changes.start
            )
        )
        if outcome.files_needing_review:
            raise UnprovenMoveError(
                changes.pull_request.number,
                tuple(file.change.path for file in outcome.files_needing_review),
            )
