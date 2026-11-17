"""
Finding the renames a pull request makes throughout from its diff alone.
"""

from __future__ import annotations

import difflib
import tokenize
from collections.abc import Iterator
from dataclasses import dataclass

from basstler.class_property import classproperty
from basstler.git.commit_range import FileVersions
from basstler.github.pull_request_changes import PullRequestChanges
from basstler.review_triage.commit_tree import CommitModules
from basstler.review_triage.comparison import PythonComparison
from basstler.review_triage.python_source import PythonSource
from basstler.review_triage.rename_sources import RenameSource
from basstler.review_triage.renames import (
    MemberRename,
    Rename,
    RenameCandidates,
    RenameDecisions,
)

# %% detection


@dataclass(frozen=True)
class RenameDetection(RenameSource):
    """
    Detects a rename as an identifier the diff consistently replaces by another, where
    the old identifier is gone from the head commit and the new one absent from the base
    commit.
    """

    @classproperty
    def label(cls) -> str:
        return "diff"

    def decisions(self, changes: PullRequestChanges) -> RenameDecisions:
        candidates = RenameCandidates()
        for change in changes.files:
            if PythonComparison().applies_to(change):
                self.collect(
                    PythonSource(change.base_text),
                    PythonSource(change.head_text),
                    candidates,
                )
        base = changes.commits.base_tree
        head = changes.commits.head_tree
        return RenameDecisions(
            tuple(
                Rename(old, new, self)
                for old, new in sorted(candidates.consistent().items())
                if not head.mentions(old) and not base.mentions(new)
            )
        )

    @staticmethod
    def collect(
        base: PythonSource, head: PythonSource, candidates: RenameCandidates
    ) -> None:
        """
        Add each identifier the head version puts in place of another to *candidates*.

        :param base: The file's base version.
        :param head: The file's head version.
        :param candidates: The substitutions found so far.
        """
        lines = difflib.SequenceMatcher(
            a=base.text.splitlines(), b=head.text.splitlines(), autojunk=False
        )
        for tag, base_start, base_end, head_start, head_end in lines.get_opcodes():
            if tag == "replace":
                RenameDetection.collect_tokens(
                    base.tokens_on_lines(base_start + 1, base_end + 1),
                    head.tokens_on_lines(head_start + 1, head_end + 1),
                    candidates,
                )

    @staticmethod
    def collect_tokens(
        base_tokens: tuple[tokenize.TokenInfo, ...],
        head_tokens: tuple[tokenize.TokenInfo, ...],
        candidates: RenameCandidates,
    ) -> None:
        """
        Add each identifier of a replaced block of lines that the head version puts in
        place of another to *candidates*.

        :param base_tokens: The block's significant tokens in the base version.
        :param head_tokens: Those of the lines replacing it in the head version.
        :param candidates: The substitutions found so far.
        """
        matcher = difflib.SequenceMatcher(
            a=[token.string for token in base_tokens],
            b=[token.string for token in head_tokens],
            autojunk=False,
        )
        for tag, base_start, base_end, head_start, head_end in matcher.get_opcodes():
            if tag != "replace" or base_end - base_start != head_end - head_start:
                continue
            for base_token, head_token in zip(
                base_tokens[base_start:base_end],
                head_tokens[head_start:head_end],
                strict=True,
            ):
                if PythonSource.is_identifier(
                    base_token
                ) and PythonSource.is_identifier(head_token):
                    candidates.add(base_token.string, head_token.string)


# %% renamed module members


@dataclass(frozen=True)
class MemberRenameDetection(RenameSource):
    """
    Detects a rename of a module's top-level definition: the module binds a new name in
    place of an old one, and the diff puts that new name in place of the old one.
    """

    @classproperty
    def label(cls) -> str:
        return "binding"

    def decisions(self, changes: PullRequestChanges) -> RenameDecisions:
        modules = [
            change for change in changes.files if PythonComparison().applies_to(change)
        ]
        sources = {
            change.path: (
                PythonSource(change.base_text),
                PythonSource(change.head_text),
            )
            for change in modules
        }
        candidates = RenameCandidates()
        for base, head in sources.values():
            RenameDetection.collect(base, head, candidates)
        base_modules = CommitModules(changes.commits.base_tree)
        head_modules = CommitModules(changes.commits.head_tree)
        renames = [
            rename
            for change in modules
            for rename in self.member_renames(
                change,
                *sources[change.path],
                candidates,
                base_modules,
                head_modules,
            )
        ]
        return RenameDecisions(tuple(sorted(renames, key=lambda rename: rename.old)))

    def member_renames(
        self,
        change: FileVersions,
        base: PythonSource,
        head: PythonSource,
        candidates: RenameCandidates,
        base_modules: CommitModules,
        head_modules: CommitModules,
    ) -> Iterator[MemberRename]:
        """
        :param change: A Python file the pull request changes.
        :param base: Its base version.
        :param head: Its head version.
        :param candidates: Every substitution the pull request's diff makes.
        :param base_modules: The base commit's modules.
        :param head_modules: The head commit's modules.
        :return: The renames of its top-level names, when the file is the only one
            of the base commit importable by its dotted path.
        """
        if not (base.parses and head.parses):
            return
        module = base_modules.module_path(change.previous_path or change.path)
        if len(base_modules.module_files.get(module, ())) != 1:
            return
        head_module = head_modules.module_path(change.path)
        added = head.defined_names - base.defined_names
        for old in sorted(base.defined_names - head.defined_names):
            news = candidates.replacements.get(old, set()) & added
            if len(news) == 1:
                yield MemberRename(
                    f"{module}.{old}", f"{head_module}.{news.pop()}", self
                )
