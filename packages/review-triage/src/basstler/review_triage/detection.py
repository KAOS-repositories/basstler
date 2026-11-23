"""
Finding the renames a pull request makes throughout from its diff alone.
"""

from __future__ import annotations

import ast
import difflib
import tokenize
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import cache

from basstler.class_property import classproperty
from basstler.git.commit_range import FileVersions
from basstler.github.pull_request_changes import PullRequestChanges
from basstler.review_triage.commit_tree import CommitModules
from basstler.review_triage.comparison import PythonComparison
from basstler.review_triage.python_source import PythonSource
from basstler.review_triage.referents import MemberResolver, defined_attribute_names
from basstler.review_triage.rename_sources import RenameSource
from basstler.review_triage.renames import (
    AttributeRename,
    ClassAttribute,
    MemberRename,
    ModuleMember,
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
                    PythonSource.from_text(change.base_text),
                    PythonSource.from_text(change.head_text),
                    candidates,
                )
        consistent = candidates.consistent()
        kept_in_head = changes.commits.head_tree.mentioned_words(frozenset(consistent))
        already_in_base = changes.commits.base_tree.mentioned_words(
            frozenset(consistent.values())
        )
        return RenameDecisions(
            tuple(
                Rename(old, new, self)
                for old, new in sorted(consistent.items())
                if old not in kept_in_head and new not in already_in_base
            )
        )

    @staticmethod
    def collect(
        base: PythonSource, head: PythonSource, candidates: RenameCandidates
    ) -> None:
        """
        Add each identifier the head version puts in place of another to *candidates*,
        none when either version is not valid Python.

        :param base: The file's base version.
        :param head: The file's head version.
        :param candidates: The substitutions found so far.
        """
        if not (base.parses and head.parses):
            return
        candidates.add_all(RenameDetection.file_candidates(base, head))

    @staticmethod
    @cache
    def file_candidates(base: PythonSource, head: PythonSource) -> RenameCandidates:
        """
        :param base: The file's base version.
        :param head: The file's head version.
        :return: Each identifier the head version puts in place of another; not to be
            modified, as it is kept for the next call.
        """
        candidates = RenameCandidates()
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
        return candidates

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


# %% renamed module and class members

PRIVATE_PREFIX = "__"
"""
The start of a name Python mangles inside its class or reserves for itself, never
detected as renamed.
"""


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
                PythonSource.from_text(change.base_text),
                PythonSource.from_text(change.head_text),
            )
            for change in modules
        }
        candidates = RenameCandidates()
        for base, head in sources.values():
            RenameDetection.collect(base, head, candidates)
        base_modules = CommitModules(changes.commits.base_tree)
        head_modules = CommitModules(changes.commits.head_tree)
        renames: list[Rename] = []
        attributes: dict[ClassAttribute, AttributeRename] = {}
        for change in modules:
            for rename in self.member_renames(
                change,
                *sources[change.path],
                candidates,
                base_modules,
                head_modules,
            ):
                if isinstance(rename, AttributeRename):
                    attributes[rename.attribute] = rename
                else:
                    renames.append(rename)
        renames.extend(
            HierarchyCheck(MemberResolver(base_modules)).consistent(attributes)
        )
        return RenameDecisions(tuple(sorted(renames, key=lambda rename: rename.old)))

    def member_renames(
        self,
        change: FileVersions,
        base: PythonSource,
        head: PythonSource,
        candidates: RenameCandidates,
        base_modules: CommitModules,
        head_modules: CommitModules,
    ) -> Iterator[MemberRename | AttributeRename]:
        """
        :param change: A Python file the pull request changes.
        :param base: Its base version.
        :param head: Its head version.
        :param candidates: Every substitution the pull request's diff makes.
        :param base_modules: The base commit's modules.
        :param head_modules: The head commit's modules.
        :return: The renames of its top-level names and of the attributes of its
            top-level classes, when the file is the only one of the base commit
            importable by its dotted path; those of attributes not checked against
            their class hierarchy yet.
        """
        if not (base.parses and head.parses):
            return
        module = base_modules.module_path(change.previous_path or change.path)
        if len(base_modules.module_files.get(module, ())) != 1:
            return
        head_module = head_modules.module_path(change.path)
        members = candidates.dominant_pairs(
            base.defined_names - head.defined_names,
            head.defined_names - base.defined_names,
        )
        for old, new in sorted(members.items()):
            yield MemberRename(f"{module}.{old}", f"{head_module}.{new}", self)
        head_classes = self.top_level_classes(head)
        for name, definition in sorted(self.top_level_classes(base).items()):
            head_name = members.get(name, name)
            if head_name not in head_classes:
                continue
            base_names = defined_attribute_names(definition)
            head_names = defined_attribute_names(head_classes[head_name])
            pairs = candidates.dominant_pairs(
                base_names - head_names, head_names - base_names
            )
            for old, new in sorted(pairs.items()):
                if PRIVATE_PREFIX not in (old[:2], new[:2]):
                    yield AttributeRename.from_attribute(
                        ClassAttribute(ModuleMember(module, name), old),
                        ModuleMember(head_module, head_name),
                        new,
                        self,
                    )

    @staticmethod
    def top_level_classes(source: PythonSource) -> dict[str, ast.ClassDef]:
        """
        :param source: A module.
        :return: The classes its top level defines, by name, those it defines more
            than once left out.
        """
        classes = [
            statement
            for statement in source.tree.body
            if isinstance(statement, ast.ClassDef)
        ]
        counts = Counter(definition.name for definition in classes)
        return {
            definition.name: definition
            for definition in classes
            if counts[definition.name] == 1
        }


# %% renames consistent across a class hierarchy


@dataclass
class HierarchyCheck:
    """
    Keeps only the renames of class attributes that every class overriding them or
    overridden by them makes alike, so that a renamed method still overrides what it
    did.
    """

    resolver: MemberResolver
    """
    What the base commit's names refer to.
    """

    subclasses: dict[
        ModuleMember, list[tuple[ModuleMember | None, ast.ClassDef]] | None
    ] = field(default_factory=dict)
    """
    The classes that may inherit from each class looked up so far.
    """

    def consistent(
        self, renames: dict[ClassAttribute, AttributeRename]
    ) -> list[AttributeRename]:
        """
        :param renames: The renames of class attributes, by the attribute renamed.
        :return: Those consistent with the renames kept, dropped until none changes.
        """
        kept = dict(renames)
        dropped = True
        while dropped:
            dropped = False
            for attribute, rename in list(kept.items()):
                if not self.is_consistent(rename, kept):
                    del kept[attribute]
                    dropped = True
        return list(kept.values())

    def is_consistent(
        self, rename: AttributeRename, kept: dict[ClassAttribute, AttributeRename]
    ) -> bool:
        """
        :param rename: The rename of a class attribute.
        :param kept: The renames of class attributes kept so far.
        :return: Whether no ancestor or possible subclass of its class defines the new
            name, and each that defines the old name renames it alike.
        """
        owner = rename.attribute.owner
        if owner not in self.subclasses:
            self.subclasses[owner] = self.resolver.possible_subclasses(owner)
        subclasses = self.subclasses[owner]
        ancestors = self.resolver.defining_ancestors(owner, rename.old_name)
        if (
            subclasses is None
            or ancestors is None
            or self.resolver.defining_ancestors(owner, rename.new_name) != ()
        ):
            return False
        for identity, definition in subclasses:
            names = defined_attribute_names(definition)
            if rename.new_name in names or (
                rename.old_name in names
                and not self.is_renamed_alike(identity, rename, kept)
            ):
                return False
        return all(
            self.is_renamed_alike(ancestor, rename, kept) for ancestor in ancestors
        )

    @staticmethod
    def is_renamed_alike(
        member: ModuleMember | None,
        rename: AttributeRename,
        kept: dict[ClassAttribute, AttributeRename],
    ) -> bool:
        """
        :param member: A class overriding or overridden by the renamed attribute,
            ``None`` when it is no module's top-level class.
        :param rename: The rename of a class attribute.
        :param kept: The renames of class attributes kept so far.
        :return: Whether the class's attribute of the old name is renamed to the same
            new name.
        """
        if member is None:
            return False
        other = kept.get(ClassAttribute(member, rename.old_name))
        return other is not None and other.new_name == rename.new_name
