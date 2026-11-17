"""
The identifiers a pull request renames throughout, and their application to code and
prose.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from basstler.review_triage.rename_sources import RenameSource

# %% one rename


@dataclass(frozen=True)
class Rename:
    """
    One identifier, or one dotted module path, replaced by another wherever it occurs.
    """

    old: str
    """
    The identifier the base commit uses, dotted when it names a module.
    """

    new: str
    """
    The identifier the head commit uses in its place.
    """

    found_by: RenameSource
    """
    The rename source that found it.
    """

    is_file_path: bool = False
    """
    Whether both sides are file paths, which never occur inside code.
    """

    def is_rejected_by(self, rejected: str) -> bool:
        """
        :param rejected: An old identifier a rename source rejects.
        :return: Whether that rejects this rename.
        """
        return self.old == rejected

    def is_repeated_in(self, renames: dict[str, Rename]) -> bool:
        """
        :param renames: The renames applied together, by their old identifier.
        :return: Whether another of them already makes this one.
        """
        return False


@dataclass(frozen=True)
class ModuleMember:
    """
    A name a module binds at its top level, such as a class it defines.
    """

    module: str
    """
    The module's dotted path.
    """

    member_name: str
    """
    The name the module binds.
    """


@dataclass(frozen=True)
class MemberRename(Rename):
    """
    A module's top-level definition given a new name, by its qualified path: it renames
    only the occurrences proven to refer to that definition, never its old name as a
    word.
    """

    @property
    def member(self) -> ModuleMember:
        """
        The definition renamed, as the base commit names it.
        """
        module, _, member_name = self.old.rpartition(DOTTED_NAME_SEPARATOR)
        return ModuleMember(module, member_name)

    @property
    def new_member_name(self) -> str:
        """
        The name the head commit gives the definition.
        """
        return self.new.rpartition(DOTTED_NAME_SEPARATOR)[2]

    def is_rejected_by(self, rejected: str) -> bool:
        """
        :meth:`Rename.is_rejected_by`, also when the member's old name is rejected.
        """
        return rejected in (self.old, self.member.member_name)

    def is_repeated_in(self, renames: dict[str, Rename]) -> bool:
        """
        :meth:`Rename.is_repeated_in`: whether the member's old name is renamed to its
        new name everywhere.
        """
        word = renames.get(self.member.member_name)
        return word is not None and word.new == self.new_member_name


@dataclass(frozen=True)
class RenameDecisions:
    """
    What one rename source decides: renames it accepts and old identifiers it rejects.
    """

    accepted: tuple[Rename, ...] = ()
    """
    The renames the source finds.
    """

    rejected: frozenset[str] = frozenset()
    """
    Old identifiers whose rename, found by an earlier source, is not a rename.
    """


# %% every rename of a pull request

DOTTED_NAME_SEPARATOR = "."
"""
What separates the components of a dotted module or attribute path.
"""

IMPORT_LINE_PATTERN = (
    r"^(?P<lead>[ 	]*from[ 	]+)(?P<module>[\w.]+)"
    r"(?P<middle>[ 	]+import[ 	]+)(?P<name>\w+)"
)
"""
Matches the start of an import statement in prose, such as a documentation code block,
up to the first name it imports.
"""


@dataclass(frozen=True)
class RenameMap:
    """
    The renames applied together, each identifier mapped to at most one replacement.
    """

    renames: tuple[Rename, ...] = ()
    """
    The renames, ordered by their old identifier.
    """

    @classmethod
    def from_decisions(cls, decisions: Iterable[RenameDecisions]) -> RenameMap:
        """
        :param decisions: The decisions of each rename source, a later source's
            outranking an earlier one's.
        :return: The renames left once every decision is applied.
        """
        renames: dict[str, Rename] = {}
        for decision in decisions:
            for rejected in decision.rejected:
                renames = {
                    old: rename
                    for old, rename in renames.items()
                    if not rename.is_rejected_by(rejected)
                }
            renames |= {rename.old: rename for rename in decision.accepted}
        return cls(
            tuple(
                renames[old]
                for old in sorted(renames)
                if not renames[old].is_repeated_in(renames)
            )
        )

    @cached_property
    def identifier_renames(self) -> tuple[Rename, ...]:
        """
        The renames of identifiers and module paths, those of file paths left out.
        """
        return tuple(rename for rename in self.renames if not rename.is_file_path)

    @cached_property
    def member_renames(self) -> tuple[MemberRename, ...]:
        """
        The renames of module members, which rename only what refers to them.
        """
        return tuple(
            rename for rename in self.renames if isinstance(rename, MemberRename)
        )

    @cached_property
    def replacements(self) -> dict[str, str]:
        """
        The new identifier of each old one.
        """
        return {rename.old: rename.new for rename in self.renames}

    @cached_property
    def word_pattern(self) -> re.Pattern[str] | None:
        """
        Matches any old identifier as a whole word, ``None`` when there are no renames.
        """
        if not self.renames:
            return None
        alternatives = [
            self.whole_word_pattern(rename)
            for rename in sorted(
                self.renames, key=lambda rename: len(rename.old), reverse=True
            )
        ]
        return re.compile("|".join(alternatives))

    @staticmethod
    def whole_word_pattern(rename: Rename) -> str:
        """
        :param rename: A rename.
        :return: What matches its old side only where it stands whole; a file path
            never as the end of a longer path.
        """
        if not rename.is_file_path:
            return rf"\b{re.escape(rename.old)}\b"
        return rf"(?<![\w/.-]){re.escape(rename.old)}(?![\w/-])"

    @cached_property
    def renamed_modules(self) -> tuple[str, ...]:
        """
        The old dotted module paths, longest first.
        """
        return tuple(
            sorted(
                (
                    rename.old
                    for rename in self.renames
                    if DOTTED_NAME_SEPARATOR in rename.old and not rename.is_file_path
                ),
                key=len,
                reverse=True,
            )
        )

    def renamed_identifier(self, identifier: str) -> str:
        """
        :param identifier: A name, or a dotted path of names.
        :return: It with its longest renamed module prefix replaced, then every
            other component that is renamed.
        """
        prefix = ""
        for module in self.renamed_modules:
            if identifier == module or identifier.startswith(
                module + DOTTED_NAME_SEPARATOR
            ):
                prefix = self.replacements[module]
                identifier = identifier.removeprefix(module)
                break
        return prefix + DOTTED_NAME_SEPARATOR.join(
            self.replacements.get(component, component)
            for component in identifier.split(DOTTED_NAME_SEPARATOR)
        )

    def original_identifier(self, identifier: str) -> str:
        """
        :param identifier: A name the head commit uses.
        :return: The name the base commit used in its place.
        """
        return next(
            (rename.old for rename in self.renames if rename.new == identifier),
            identifier,
        )

    @cached_property
    def prose_pattern(self) -> re.Pattern[str] | None:
        """
        Matches an import statement's start or an old identifier as a whole word,
        ``None`` when there are no renames.
        """
        if self.word_pattern is None:
            return None
        return re.compile(
            f"{IMPORT_LINE_PATTERN}|{self.word_pattern.pattern}", re.MULTILINE
        )

    def renamed_prose(self, text: str) -> str:
        """
        :param text: Prose, such as a docstring, a comment or a documentation file.
        :return: It with every old identifier occurring as a whole word replaced, and
            the module and first name of every import statement following the renames.
        """
        if self.prose_pattern is None:
            return text
        return self.prose_pattern.sub(self.renamed_match, text)

    def renamed_match(self, match: re.Match[str]) -> str:
        """
        :param match: An import statement's start or an old identifier in prose.
        :return: What replaces it.
        """
        if match.group("module") is None:
            return self.replacements[match.group()]
        module, _, name = self.renamed_identifier(
            f"{match.group('module')}{DOTTED_NAME_SEPARATOR}{match.group('name')}"
        ).rpartition(DOTTED_NAME_SEPARATOR)
        return f"{match.group('lead')}{module}{match.group('middle')}{name}"


# %% candidate renames found in a diff


@dataclass
class RenameCandidates:
    """
    Identifier substitutions seen in a pull request's diff, with how often each was seen.
    """

    replacements: dict[str, Counter[str]] = field(default_factory=dict)
    """
    How often each old identifier was seen replaced by each new identifier.
    """

    def add(self, old: str, new: str) -> None:
        """
        Record that *old* was replaced by *new* at one place.

        :param old: The identifier in the base version.
        :param new: The identifier in its place in the head version.
        """
        self.replacements.setdefault(old, Counter())[new] += 1

    def consistent(self) -> dict[str, str]:
        """
        :return: The replacement of each old identifier only ever replaced by one.
        """
        return {
            old: next(iter(news))
            for old, news in self.replacements.items()
            if len(news) == 1
        }

    def dominant_pairs(
        self, olds: frozenset[str], news: frozenset[str]
    ) -> dict[str, str]:
        """
        :param olds: Old identifiers.
        :param news: New identifiers.
        :return: The new identifier of each old one, where of these each is the
            other's most frequent counterpart and no other ties with it.
        """
        counts = {
            (old, new): count
            for old in olds
            for new, count in self.replacements.get(old, Counter()).items()
            if new in news
        }
        best_news = self.most_frequent(
            {
                old: {new: k for (o, new), k in counts.items() if o == old}
                for old in olds
            }
        )
        best_olds = self.most_frequent(
            {
                new: {old: k for (old, n), k in counts.items() if n == new}
                for new in news
            }
        )
        return {old: new for old, new in best_news.items() if best_olds.get(new) == old}

    @staticmethod
    def most_frequent(counterparts: dict[str, dict[str, int]]) -> dict[str, str]:
        """
        :param counterparts: How often each identifier was paired with each other.
        :return: The counterpart each identifier was paired with more often than with
            any other.
        """
        found = {}
        for identifier, counts in counterparts.items():
            ranked = sorted(counts.items(), key=lambda item: item[1], reverse=True)
            if ranked and (len(ranked) == 1 or ranked[0][1] > ranked[1][1]):
                found[identifier] = ranked[0][0]
        return found
