"""
A pull request's change split into a commit making only changes the triage proves
mechanical and one making every other change, so a reviewer reads only the second.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import PurePosixPath

from basstler.class_property import classproperty
from basstler.git.commands import CommitTrailer, GitCommandRunner
from basstler.git.commit_range import CommitRange, FileVersions
from basstler.github.constants import MaintenanceText
from basstler.github.pull_request_changes import (
    PullRequestChanges,
    RestPullRequest,
    StartCommit,
    StartReason,
)
from basstler.github.pull_request_description import PullRequestDescription
from basstler.locations import ReviewTriageLocation
from basstler.render_common import TemplatePage
from basstler.review_triage.comparison import (
    FileTriager,
    MechanicalFile,
    PythonComparison,
)
from basstler.review_triage.definition_moves import DefinitionMoveComparison
from basstler.review_triage.exceptions import BaseBranchMergedError, UnprovenSplitError
from basstler.review_triage.moved_definitions import MovedDefinition, MovedDefinitions
from basstler.review_triage.python_source import LineSpan, PythonSource
from basstler.review_triage.source_renaming import SourceRenaming
from basstler.review_triage.statement_merge import StatementMerge
from basstler.review_triage.triage import PullRequestTriager, TriageOutcome

FUTURE_MODULE = "__future__"
"""
The module whose imports switch on features of later Python versions, kept apart above
every other import.
"""

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
        if change.base_text is None and self.moved.arriving_at(change.path):
            return self.added_module_text(change)
        base_path = change.previous_path or change.path
        text = (
            self.cut(base_path) if self.moved.leaving(base_path) else change.base_text
        )
        if not self.moved.arriving_at(change.path):
            return text
        return self.pasted(change.path, text or "").removesuffix("\n")

    def added_module_text(self, change: FileVersions) -> str:
        """
        :param change: A module the pull request adds and definitions move into.
        :return: Its docstring, the imports the arriving definitions use, and those
            definitions in their base versions, in the order the head version holds
            them; a name is imported as the module it left imports it, otherwise as
            the head version does.
        """
        head = PythonSource(change.head_text or "")
        arriving = sorted(
            self.moved.arriving_at(change.path),
            key=lambda moved: head.definition_span(moved.new_name).first,
        )
        definitions = [self.base_lines(moved) for moved in arriving]
        used = PythonSource("".join(definitions)).referenced_names(
            self.triager.context.renames
        )
        sources = list(dict.fromkeys(moved.source_text for moved in arriving))
        source_imports = [
            kept
            for text in sources
            for statement in PythonSource(text).tree.body
            if (kept := self.used_imports(statement, used)) is not None
        ]
        imported = frozenset(
            alias.asname or alias.name.partition(".")[0]
            for statement in source_imports
            for node in ast.walk(statement)
            if isinstance(node, ast.Import | ast.ImportFrom)
            for alias in node.names
        )
        body = head.tree.body
        documented = bool(body) and PythonSource.is_documentation(body[0])
        head_imports = [
            kept
            for statement in body[documented:]
            if (kept := self.used_imports(statement, used - imported)) is not None
        ]
        statements = (*source_imports, *head_imports)
        future = [
            ast.unparse(statement)
            for statement in statements
            if isinstance(statement, ast.ImportFrom)
            and statement.module == FUTURE_MODULE
        ]
        imports = [
            ast.unparse(statement)
            for statement in statements
            if not (
                isinstance(statement, ast.ImportFrom)
                and statement.module == FUTURE_MODULE
            )
        ]
        preamble = [
            *(
                [head.lines_of(LineSpan(1, body[0].end_lineno or 1))]
                if documented
                else []
            ),
            *(["\n".join(dict.fromkeys(future))] if future else []),
            *(["\n".join(dict.fromkeys(imports))] if imports else []),
        ]
        return "\n\n\n".join(
            [
                "\n\n".join(part.rstrip("\n") for part in preamble),
                *(definition.rstrip("\n") for definition in definitions),
            ]
        )

    @staticmethod
    def used_imports(statement: ast.stmt, used: frozenset[str]) -> ast.stmt | None:
        """
        :param statement: A top-level statement of a module.
        :param used: The names the module's code uses.
        :return: The import keeping only the names it binds that are used, or a
            condition holding only imports keeping only those; ``None`` when nothing
            is left or the statement is neither.
        """
        if isinstance(statement, ast.ImportFrom) and statement.module == FUTURE_MODULE:
            return statement
        if not PythonSource.is_import(statement):
            return None
        if isinstance(statement, ast.If):
            inner = [
                kept
                for nested in statement.body
                if (kept := MechanicalTree.used_imports(nested, used)) is not None
            ]
            return ast.If(test=statement.test, body=inner, orelse=[]) if inner else None
        if isinstance(statement, ast.Import):
            names = MechanicalTree.used_aliases(statement.names, used)
            return ast.Import(names=names) if names else None
        names = MechanicalTree.used_aliases(statement.names, used)
        if not names:
            return None
        return ast.ImportFrom(
            module=statement.module, names=names, level=statement.level
        )

    @staticmethod
    def used_aliases(aliases: list[ast.alias], used: frozenset[str]) -> list[ast.alias]:
        """
        :param aliases: The names an import binds.
        :param used: The names the module's code uses.
        :return: Those of them the code uses.
        """
        return [
            alias
            for alias in aliases
            if (alias.asname or alias.name.partition(".")[0]) in used
        ]

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

    def base_lines(self, moved: MovedDefinition) -> str:
        """
        :param moved: A moved definition.
        :return: Its lines in the module it left, the occurrences proven to refer to a
            renamed member renamed, its own name among them.
        """
        source = DefinitionMoveComparison.renamed_source(moved, self.triager.context)
        return source.lines_of(source.definition_span(moved.name_in(source)))

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


class SplitCommitRole(StrEnum):
    """
    The part a commit plays in a split, as its :attr:`CommitTrailer.SPLIT` trailer
    names it.
    """

    WHOLE_MECHANICAL = "whole-mechanical"
    """
    Makes every mechanical change of the pull request, on the previous such commit or
    on the merge base.
    """
    WHOLE_REMAINING = "whole-remaining"
    """
    Merges the head into the whole mechanical commit, so its own change is every other
    change of the pull request.
    """
    PUSH_MECHANICAL = "push-mechanical"
    """
    Makes the mechanical changes pushed since the previous split, on that split.
    """
    PUSH_REMAINING = "push-remaining"
    """
    Merges the head into the push's mechanical commit, so its own change is every other
    change pushed since the previous split.
    """

    def message(self, number: int, details: str) -> str:
        """
        :param number: The pull request's number.
        :param details: The paragraphs below the title.
        :return: The message of a commit playing this part in a split of the pull
            request, ending in the trailer naming the part.
        """
        match self:
            case SplitCommitRole.WHOLE_MECHANICAL:
                title = f"Make the mechanical changes of #{number}"
            case SplitCommitRole.WHOLE_REMAINING:
                title = f"Make the changes of #{number} beyond the mechanical ones"
            case SplitCommitRole.PUSH_MECHANICAL:
                title = f"Make the mechanical changes of #{number} since the last split"
            case SplitCommitRole.PUSH_REMAINING:
                title = (
                    f"Make the changes of #{number} since the last split beyond the "
                    f"mechanical ones"
                )
        return f"{title}\n\n{details}\n\n{CommitTrailer.SPLIT}: {self}"


@dataclass(frozen=True)
class ProvenMechanicalTree:
    """
    The tree of a commit making a change's mechanical changes, with the triage proving
    it.
    """

    tree: str
    """
    The tree.
    """

    outcome: TriageOutcome
    """
    The triage proving every change it makes mechanical.
    """


@dataclass(frozen=True)
class MechanicalSplit:
    """
    The commits a split adds on top of a pull request's head, the last of them its new
    head: one whose own change is every change of the pull request beyond the mechanical
    ones and, after an earlier split, one whose own change is every such change pushed
    since.
    """

    pull_request: RestPullRequest
    """
    The pull request split.
    """

    mechanical_commit: str
    """
    The commit making every mechanical change of the pull request.
    """

    remaining_commit: str
    """
    The merge of the head into :attr:`mechanical_commit`, holding the head's tree.
    """

    outcome: TriageOutcome | None = field(compare=False)
    """
    The triage proving :attr:`mechanical_commit` mechanical, ``None`` when the pull
    request has no mechanical change left.
    """

    push_mechanical_commit: str | None = None
    """
    The commit making the mechanical changes pushed since the previous split, ``None``
    when there are none or the split is the first.
    """

    push_remaining_commit: str | None = None
    """
    The merge of the head into the commit making the mechanical changes pushed since
    the previous split, holding the head's tree; ``None`` when the split is the first
    or a push merged the base branch in.
    """

    def description(self, pull_request_url: str) -> str:
        """
        :param pull_request_url: The pull request's page.
        :return: Its description with the split's links and summary as its mechanical
            changes section, replacing any section already there.
        """
        since = (
            ""
            if self.push_remaining_commit is None
            else (
                f" Since the previous split, review [the changes pushed]"
                f"({pull_request_url}/commits/{self.push_remaining_commit})."
            )
        )
        summary = (
            ""
            if self.outcome is None
            else f"\n\n{MechanicalSummary().render(self.outcome)}"
        )
        content = (
            f"{self.mechanical_commit} makes only changes `basstler review-triage` "
            f"proves mechanical; review [every other change]({pull_request_url}/"
            f"commits/{self.remaining_commit}).{since}{summary}"
        )
        return PullRequestDescription(self.pull_request.description).with_section(
            MaintenanceText.MECHANICAL_CHANGES_HEADING, content
        )

    def publish(self, git: GitCommandRunner, location: str) -> None:
        """
        Advance the pull request's branch to :attr:`remaining_commit`, which descends
        from its head, refused when the branch has moved since the pull request was
        read.

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
    Splits pull requests into their mechanical changes and the rest by adding commits on
    top of their heads, proving each mechanical commit mechanical.
    """

    git: GitCommandRunner
    """
    The checkout holding the pull requests' commits.
    """

    triager: PullRequestTriager = field(default_factory=PullRequestTriager)
    """
    Judges the files and proves the mechanical commits mechanical.
    """

    def split(self, changes: PullRequestChanges) -> MechanicalSplit | None:
        """
        :param changes: A pull request's whole change, from its merge base.
        :return: Its split, dated as its head commit so the same branch always splits
            into the same commits; ``None`` when its head is a split already, or when no
            split was made before and its change is wholly mechanical or has nothing
            mechanical.
        :raises BaseBranchMergedError: If the base branch was merged into it since the
            commit its change starts from.
        :raises UnprovenSplitError: If a mechanical commit changes a file the triage
            cannot prove mechanical.
        """
        head = changes.commits.head_commit
        previous = self.git.newest_commit_with_trailer(
            head,
            changes.commits.base_commit,
            CommitTrailer.SPLIT,
            SplitCommitRole.WHOLE_REMAINING,
        )
        if previous == head:
            return None
        whole = self.proven_tree(changes)
        if previous is not None:
            return self.later_split(changes, previous, whole)
        if whole is None or whole.tree == self.git.tree_of(head):
            return None
        mechanical = self.commit(
            changes,
            whole.tree,
            (changes.commits.base_commit,),
            SplitCommitRole.WHOLE_MECHANICAL,
            MechanicalSummary().render(whole.outcome),
        )
        return MechanicalSplit(
            changes.pull_request,
            mechanical,
            self.merged_head(
                changes, mechanical, head, SplitCommitRole.WHOLE_REMAINING
            ),
            whole.outcome,
        )

    def later_split(
        self,
        changes: PullRequestChanges,
        previous: str,
        whole: ProvenMechanicalTree | None,
    ) -> MechanicalSplit:
        """
        :param changes: A pull request's whole change, from its merge base.
        :param previous: The last commit the previous split added.
        :param whole: The proven tree making every mechanical change of the pull
            request, ``None`` when it has none.
        :return: The split adding, on the previous split, the commits making the
            mechanical changes pushed since and merging the head into them, unless a push
            merged the base branch in; then the whole mechanical commit, unless it is
            unchanged, and the merge of those into it.
        """
        head = changes.commits.head_commit
        previous_mechanical = self.git.parents_of(previous)[0]
        tree = (
            self.git.tree_of(changes.commits.base_commit)
            if whole is None
            else whole.tree
        )
        mechanical = (
            previous_mechanical
            if tree == self.git.tree_of(previous_mechanical)
            else self.commit(
                changes,
                tree,
                (previous_mechanical,),
                SplitCommitRole.WHOLE_MECHANICAL,
                "" if whole is None else MechanicalSummary().render(whole.outcome),
            )
        )
        outcome = None if whole is None else whole.outcome
        if self.base_branch_merged_since(changes, previous):
            return MechanicalSplit(
                changes.pull_request,
                mechanical,
                self.merged_head(
                    changes, mechanical, head, SplitCommitRole.WHOLE_REMAINING
                ),
                outcome,
            )
        pushed = PullRequestChanges(
            changes.pull_request,
            CommitRange(self.git, previous, head),
            CommitRange(self.git, previous, head).file_versions(),
            StartCommit(previous, StartReason.PREVIOUS_SPLIT),
        )
        push = self.proven_tree(pushed)
        push_mechanical = (
            None
            if push is None
            else self.commit(
                changes,
                push.tree,
                (previous,),
                SplitCommitRole.PUSH_MECHANICAL,
                MechanicalSummary().render(push.outcome),
            )
        )
        push_remaining = self.merged_head(
            changes, push_mechanical or previous, head, SplitCommitRole.PUSH_REMAINING
        )
        return MechanicalSplit(
            changes.pull_request,
            mechanical,
            self.merged_head(
                changes, mechanical, push_remaining, SplitCommitRole.WHOLE_REMAINING
            ),
            outcome,
            push_mechanical,
            push_remaining,
        )

    def base_branch_merged_since(self, changes: PullRequestChanges, start: str) -> bool:
        """
        :param changes: A pull request's change.
        :param start: A commit of its history.
        :return: Whether the base branch was merged into its head since *start*.
        """
        base_branch = changes.pull_request.base.commit
        return self.git.merge_base(base_branch, start) != self.git.merge_base(
            base_branch, changes.commits.head_commit
        )

    def proven_tree(self, changes: PullRequestChanges) -> ProvenMechanicalTree | None:
        """
        :param changes: A pull request's change since a commit.
        :return: The proven tree making that change's mechanical changes on that
            commit, ``None`` when it has none.
        :raises BaseBranchMergedError: If the base branch was merged into the pull
            request since that commit.
        :raises UnprovenSplitError: If the tree changes a file the triage cannot prove
            mechanical.
        """
        start = changes.commits.base_commit
        if self.base_branch_merged_since(changes, start):
            raise BaseBranchMergedError(changes.pull_request.number, start)
        file_triager = self.triager.file_triager(changes)
        files = MechanicalTree(changes, file_triager).files()
        if not files:
            return None
        draft = self.git.commit_files(
            start, files.texts, "Make the mechanical changes", copied=files.copied
        )
        tree = self.git.tree_of(draft)
        if tree == self.git.tree_of(start):
            return None
        return ProvenMechanicalTree(tree, self.prove(changes, draft, file_triager))

    def commit(
        self,
        changes: PullRequestChanges,
        tree: str,
        parents: tuple[str, ...],
        role: SplitCommitRole,
        details: str,
    ) -> str:
        """
        :param changes: The pull request's change.
        :param tree: The tree the commit records.
        :param parents: Its parents, its first parent first.
        :param role: The part it plays in the split.
        :param details: The paragraphs of its message below the title.
        :return: The commit, dated as the pull request's head commit.
        """
        head = changes.commits.head_commit
        return self.git.commit_tree(
            tree,
            parents,
            role.message(changes.pull_request.number, details),
            self.git.run("show", "--no-patch", "--format=%cI", head),
        )

    def merged_head(
        self,
        changes: PullRequestChanges,
        mechanical: str,
        merged: str,
        role: SplitCommitRole,
    ) -> str:
        """
        :param changes: The pull request's change.
        :param mechanical: A commit making mechanical changes, the merge's first parent.
        :param merged: The commit merged in, holding the head's tree.
        :param role: The part the merge plays in the split.
        :return: The merge, holding the pull request's head tree.
        """
        head = changes.commits.head_commit
        return self.commit(
            changes,
            self.git.tree_of(head),
            (mechanical, merged),
            role,
            f"Its tree is that of the head {head}.",
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
