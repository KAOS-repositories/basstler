"""
A pull request's change split into a commit making only changes the triage proves
mechanical and one making every other change, so a reviewer reads only the second.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath

from basstler.class_property import classproperty
from basstler.git.commands import GitCommandRunner
from basstler.git.commit_range import CommitRange, FileVersions
from basstler.github.constants import MaintenanceText
from basstler.github.pull_request_changes import PullRequestChanges, RestPullRequest
from basstler.github.pull_request_description import PullRequestDescription
from basstler.locations import ReviewTriageLocation
from basstler.render_common import TemplatePage
from basstler.review_triage.comparison import (
    FileTriager,
    MechanicalFile,
    PythonComparison,
)
from basstler.review_triage.exceptions import BaseBranchMergedError, UnprovenSplitError
from basstler.review_triage.moved_definitions import MovedDefinition, MovedDefinitions
from basstler.review_triage.python_source import LineSpan, PythonSource
from basstler.review_triage.source_renaming import SourceRenaming
from basstler.review_triage.statement_merge import StatementMerge
from basstler.review_triage.triage import PullRequestTriager, TriageOutcome

# %% the files of the mechanical commit


@dataclass(frozen=True)
class MechanicalFiles:
    """
    What a mechanical commit writes on top of the commit it follows.
    """

    texts: dict[str, str | None] = field(default_factory=dict)
    """
    The text of each file written, by path, without its final newline; ``None`` for a
    file removed.
    """

    copied: dict[str, str] = field(default_factory=dict)
    """
    The files taken byte for byte from another commit: that commit by each file's path.
    """

    def take_head_version(self, change: FileVersions, head_commit: str) -> None:
        """
        Take a changed file's head version: its removal, or its move and content.

        :param change: A changed file.
        :param head_commit: The commit holding its head version.
        """
        if change.previous_path is not None:
            self.texts[str(change.previous_path)] = None
        if change.head_text is None and not change.is_binary:
            self.texts[str(change.path)] = None
            return
        self.copied[str(change.path)] = head_commit

    def __bool__(self) -> bool:
        return bool(self.texts or self.copied)


@dataclass(frozen=True)
class MechanicalTree:
    """
    The files of a pull request's change once only its mechanical changes are made: each
    mechanical file in its head version, and every other file with each of its statement
    changes the triage proves mechanical.
    """

    changes: PullRequestChanges
    """
    The pull request's whole change.
    """

    triager: FileTriager
    """
    Judges each file with the pull request's renames and moves.
    """

    @property
    def moved(self) -> MovedDefinitions:
        """
        The definitions the pull request moves between modules.
        """
        return self.triager.context.moved_definitions

    @property
    def changed_files(self) -> dict[PurePosixPath, FileVersions]:
        """
        Each file the pull request changes, by its head path.
        """
        return {change.path: change for change in self.changes.files}

    def files(self) -> MechanicalFiles:
        """
        :return: The files the mechanical changes change.
        """
        files = MechanicalFiles()
        for change in self.changes.files:
            if isinstance(self.triager.triage(change), MechanicalFile):
                files.take_head_version(change, self.changes.commits.head_commit)
                continue
            text = self.mechanical_text(change)
            if text == change.base_text and change.previous_path is None:
                continue
            if text is None and change.base_text is None:
                continue
            if change.previous_path is not None:
                files.texts[str(change.previous_path)] = None
            files.texts[str(change.path)] = text
        return files

    def mechanical_text(self, change: FileVersions) -> str | None:
        """
        :param change: A file whose change is not mechanical as a whole.
        :return: Its version making only the mechanical changes, ``None`` when it has
            none.
        """
        start = self.start_text(change)
        if (
            start is None
            or change.head_text is None
            or change.path.suffix not in PythonComparison.suffixes
        ):
            return start
        merge = StatementMerge(self.triager, change)
        renamed = SourceRenaming(
            PythonSource(start), self.triager.context.renames
        ).renamed_text()
        for candidate in (renamed, start):
            if merge.is_mechanical(f"{candidate}\n"):
                return merge.merged_text(candidate)
        return change.base_text

    def start_text(self, change: FileVersions) -> str | None:
        """
        :param change: A changed file.
        :return: Its base version with the definitions leaving it cut and those
            arriving at it pasted, ``None`` when it has no base version and none arrive.
        """
        base_path = change.previous_path or change.path
        text = (
            self.cut(base_path) if self.moved.leaving(base_path) else change.base_text
        )
        if not self.moved.arriving_at(change.path):
            return text
        return self.pasted(change.path, text or "").removesuffix("\n")

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
            line for number, line in enumerate(lines, start=1) if number not in removed
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
            key=lambda moved: head.definition_span(moved.new_name).first,
        )
        parts = (
            [start, *map(self.base_lines, arriving)]
            if start
            else map(self.base_lines, arriving)
        )
        return "\n\n".join(
            part if part.endswith("\n") else f"{part}\n" for part in parts
        )

    @staticmethod
    def base_lines(moved: MovedDefinition) -> str:
        """
        :param moved: A moved definition.
        :return: Its lines in the module it left, exactly as they were.
        """
        lines = moved.source_text.splitlines(keepends=True)
        span = moved.source.definition_span(moved.old_name)
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
        span = moved.source.definition_span(moved.old_name)
        first = span.first
        while first > 1 and not lines[first - 2].strip():
            first -= 1
        return LineSpan(first, span.last)


# %% the summary


class MechanicalSummary(TemplatePage):
    """
    The Markdown summary of the renames, moves and files a mechanical commit changes.
    """

    @classproperty
    def template(cls) -> str:
        return ReviewTriageLocation.MECHANICAL_SUMMARY_TEMPLATE.name

    def render(self, outcome: TriageOutcome) -> str:
        """
        :param outcome: The triage proving a mechanical commit mechanical.
        :return: The summary.
        """
        return self.render_template(outcome=outcome).strip()


# %% the split


@dataclass(frozen=True)
class MechanicalSplit:
    """
    A pull request's change as two commits on the commit its triage starts from: one
    making its mechanical changes, then one making every other change and holding its
    head's tree.
    """

    pull_request: RestPullRequest
    """
    The pull request split.
    """

    mechanical_commit: str
    """
    The commit making its mechanical changes.
    """

    remaining_commit: str
    """
    The commit making every other change, whose tree is the pull request's head tree.
    """

    outcome: TriageOutcome = field(compare=False)
    """
    The triage proving :attr:`mechanical_commit` mechanical.
    """

    def description(self, pull_request_url: str) -> str:
        """
        :param pull_request_url: The pull request's page.
        :return: Its description with the summary of the mechanical commit as its
            mechanical changes section, replacing any section already there.
        """
        content = (
            f"{self.mechanical_commit} makes only changes `basstler review-triage` "
            f"proves mechanical; review [the remaining changes]({pull_request_url}/"
            f"commits/{self.remaining_commit}).\n\n"
            f"{MechanicalSummary().render(self.outcome)}"
        )
        return PullRequestDescription(self.pull_request.description).with_section(
            MaintenanceText.MECHANICAL_CHANGES_HEADING, content
        )

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
class MechanicalSplitter:
    """
    Splits pull requests into their mechanical changes and the rest, proving the first
    commit mechanical.
    """

    git: GitCommandRunner
    """
    The checkout holding the pull requests' commits.
    """

    triager: PullRequestTriager = field(default_factory=PullRequestTriager)
    """
    Judges the files and proves the mechanical commit mechanical.
    """

    def split(self, changes: PullRequestChanges) -> MechanicalSplit | None:
        """
        :param changes: A pull request's change since the commit its triage starts
            from.
        :return: Its split, dated as its head commit so the same pull request always
            splits into the same commits; ``None`` when its change is wholly
            mechanical or has nothing mechanical.
        :raises BaseBranchMergedError: If the base branch was merged into it since that
            commit.
        :raises UnprovenSplitError: If the mechanical commit changes a file the triage
            cannot prove mechanical.
        """
        start = changes.commits.base_commit
        head = changes.commits.head_commit
        base_branch = changes.pull_request.base.commit
        if self.git.merge_base(base_branch, start) != self.git.merge_base(
            base_branch, head
        ):
            raise BaseBranchMergedError(changes.pull_request.number, start)
        file_triager = self.triager.file_triager(changes)
        files = MechanicalTree(changes, file_triager).files()
        if not files:
            return None
        draft = self.git.commit_files(
            start, files.texts, "Make the mechanical changes", copied=files.copied
        )
        tree = self.git.tree_of(draft)
        if tree == self.git.tree_of(head):
            return None
        outcome = self.prove(changes, draft, file_triager)
        date = self.git.run("show", "--no-patch", "--format=%cI", head)
        number = changes.pull_request.number
        mechanical_commit = self.git.commit_tree(
            tree,
            (start,),
            f"Make the mechanical changes of #{number}\n\n"
            f"{MechanicalSummary().render(outcome)}",
            date,
        )
        remaining_commit = self.git.commit_tree(
            self.git.tree_of(head),
            (mechanical_commit,),
            f"Make the changes of #{number} beyond the mechanical ones\n\n"
            f"Its tree is that of the former head {head}.",
            date,
        )
        return MechanicalSplit(
            changes.pull_request, mechanical_commit, remaining_commit, outcome
        )

    @staticmethod
    def prove(
        changes: PullRequestChanges, mechanical_commit: str, triager: FileTriager
    ) -> TriageOutcome:
        """
        :param changes: A pull request's change.
        :param mechanical_commit: A commit making its mechanical changes, on the commit
            its change starts from.
        :param triager: Judges files with the pull request's renames and moves.
        :return: The triage of every file the commit changes.
        :raises UnprovenSplitError: If the triage leaves any of them for review.
        """
        mechanical = CommitRange(
            changes.commits.git, changes.commits.base_commit, mechanical_commit
        )
        outcome = TriageOutcome(
            changes.pull_request,
            triager.context.renames,
            tuple(triager.triage(change) for change in mechanical.file_versions()),
            changes.start,
        )
        if outcome.files_needing_review:
            raise UnprovenSplitError(
                changes.pull_request.number,
                tuple(file.change.path for file in outcome.files_needing_review),
            )
        return outcome
