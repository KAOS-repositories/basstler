"""
Finding the definitions a pull request moves from one module to another, as renames of
their dotted paths, and judging the modules they move between.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass, field

from basstler.class_property import classproperty
from basstler.review_triage.commit_tree import (
    MODULE_SUFFIX,
    PACKAGE_INITIALIZER,
    CommitModules,
)
from basstler.review_triage.comparison import (
    ChangeKind,
    ChangeKinds,
    FileChange,
    FileJudgment,
    JudgmentContext,
    MechanicalChange,
    PythonComparison,
)
from basstler.review_triage.keyword_arguments import KeywordArgumentComparison
from basstler.review_triage.moved_definitions import MovedDefinition, MovedDefinitions
from basstler.github.pull_request_changes import PullRequestChanges
from basstler.review_triage.python_source import LineSpan, PythonSource
from basstler.review_triage.rename_sources import RenameSource
from basstler.review_triage.renames import (
    DOTTED_NAME_SEPARATOR,
    Rename,
    RenameDecisions,
    RenameMap,
)

# %% detection


class DefinitionMoveDetection(RenameSource):
    """
    Detects a top-level definition that leaves a module the head commit keeps and is
    added to exactly one other module, as a rename of its dotted path.
    """

    @classproperty
    def label(cls) -> str:
        return "definition move"

    def decisions(self, changes: PullRequestChanges) -> RenameDecisions:
        base = CommitModules(changes.commits.base_tree)
        head = CommitModules(changes.commits.head_tree)
        modules = [
            change for change in changes.files if change.path.suffix == MODULE_SUFFIX
        ]
        gained: dict[str, list[str]] = {}
        for change in modules:
            for name in self.added_names(change):
                gained.setdefault(name, []).append(head.module_path(change.path))
        renames = [
            Rename(f"{old_module}.{name}", f"{new_modules[0]}.{name}", self)
            for change in modules
            for old_module, name in self.removed_names(change, base)
            if len(new_modules := gained.get(name, [])) == 1
            and DOTTED_NAME_SEPARATOR in old_module
        ]
        return RenameDecisions(tuple(sorted(renames, key=lambda rename: rename.old)))

    def moved_definitions(
        self, changes: PullRequestChanges, renames: RenameMap
    ) -> MovedDefinitions:
        """
        :param changes: A pull request and the files it changes.
        :param renames: The renames applied in judging its files.
        :return: The definitions those renames move between modules it changes.
        """
        base = CommitModules(changes.commits.base_tree)
        head = CommitModules(changes.commits.head_tree)
        modules = [
            change
            for change in changes.files
            if change.path.suffix == MODULE_SUFFIX and change.head_text is not None
        ]
        sources = {
            base.module_path(change.previous_path or change.path): change
            for change in modules
            if change.base_text is not None
        }
        targets = {head.module_path(change.path): change for change in modules}
        moved = []
        for rename in renames.renames:
            old_module, _, name = rename.old.rpartition(DOTTED_NAME_SEPARATOR)
            source = sources.get(old_module)
            target = targets.get(rename.new.rpartition(DOTTED_NAME_SEPARATOR)[0])
            if (
                not isinstance(rename.found_by, DefinitionMoveDetection)
                or source is None
                or target is None
            ):
                continue
            moved.append(
                MovedDefinition(
                    name,
                    source.previous_path or source.path,
                    source.base_text,
                    target.path,
                    rename.old,
                    rename.new,
                )
            )
        return MovedDefinitions(tuple(moved))

    @staticmethod
    def added_names(change: FileChange) -> frozenset[str]:
        """
        :param change: A changed module.
        :return: The names its head version defines and its base version did not.
        """
        if change.head_text is None:
            return frozenset()
        head_names = PythonSource(change.head_text).defined_names
        if change.base_text is None:
            return head_names
        return head_names - PythonSource(change.base_text).defined_names

    @staticmethod
    def removed_names(
        change: FileChange, base: CommitModules
    ) -> Iterator[tuple[str, str]]:
        """
        :param change: A changed module.
        :param base: The base commit.
        :return: The module's dotted path in the base commit with each name its base
            version defines and its head version no longer does.
        """
        if change.base_text is None or change.head_text is None:
            return
        module = base.module_path(change.previous_path or change.path)
        removed = (
            PythonSource(change.base_text).defined_names
            - PythonSource(change.head_text).defined_names
        )
        for name in sorted(removed):
            yield module, name


# %% judging the modules definitions move between


@dataclass(frozen=True)
class DefinitionMoveComparison(FileJudgment):
    """
    Judges a module that definitions move into or out of by what is left once they are
    taken out, and any other Python file as :attr:`comparison` does.
    """

    comparison: PythonComparison = field(default_factory=KeywordArgumentComparison)
    """
    How what is left of a module, and every other Python file, is compared.
    """

    def applies_to(self, change: FileChange) -> bool:
        return self.comparison.applies_to(change) or (
            change.base_text is None
            and change.head_text is not None
            and change.path.suffix == MODULE_SUFFIX
            and change.path.name != PACKAGE_INITIALIZER
        )

    def changes(
        self, change: FileChange, context: JudgmentContext
    ) -> ChangeKinds | None:
        base_path = change.previous_path or change.path
        arriving = context.moved_definitions.arriving_at(change.path)
        leaving = context.moved_definitions.leaving(base_path)
        if not arriving and not leaving:
            if change.base_text is None:
                return None
            return self.comparison.changes(change, context)
        head = PythonSource(change.head_text, change.path.parent.parts)
        base = PythonSource(change.base_text or "", base_path.parent.parts)
        head_rest = head.without(self.spans(head, arriving, base))
        base_rest = base.without(self.spans(base, leaving, head))
        arrival_kinds = self.arrival_changes(head, arriving, context)
        if arrival_kinds is None or not self.imports_only_moved_names(
            base_rest, head_rest, arriving, leaving, context.renames
        ):
            return None
        rest_kinds = self.rest_changes(base_rest, head_rest, change, context)
        if rest_kinds is None:
            return None
        kinds = set(arrival_kinds | rest_kinds)
        if arriving:
            kinds.add(MechanicalChange.DEFINITIONS_MOVED_IN)
        if leaving:
            kinds.add(MechanicalChange.DEFINITIONS_MOVED_OUT)
        return frozenset(kinds)

    @staticmethod
    def spans(
        source: PythonSource,
        definitions: tuple[MovedDefinition, ...],
        other_version: PythonSource,
    ) -> tuple[LineSpan, ...]:
        """
        :param source: One version of a module.
        :param definitions: Definitions it holds that the other version does not.
        :param other_version: The module's other version.
        :return: The definitions' lines, with the section header right above each
            when the other version lacks it.
        """
        spans = tuple(
            source.definition_span(definition.name) for definition in definitions
        )
        headers = {
            header
            for span in spans
            if (header := source.header_above(span)) is not None
            and source.lines[header.first - 1] not in other_version.lines
        }
        return spans + tuple(sorted(headers, key=lambda header: header.first))

    def arrival_changes(
        self,
        head: PythonSource,
        arriving: tuple[MovedDefinition, ...],
        context: JudgmentContext,
    ) -> ChangeKinds | None:
        """
        :param head: The head version of the module definitions move into.
        :param arriving: The definitions moving into it.
        :param context: What the judgment may consult about the pull request.
        :return: How the definitions differ from their versions in the modules they
            left, ``None`` when that is not provably mechanical.
        """
        kinds: set[ChangeKind] = set()
        for definition in arriving:
            source = definition.source
            definition_kinds = self.comparison.text_changes(
                source.lines_of(source.definition_span(definition.name)),
                head.lines_of(head.definition_span(definition.name)),
                context,
            )
            if definition_kinds is None:
                return None
            kinds |= definition_kinds
        return frozenset(kinds)

    @staticmethod
    def imports_only_moved_names(
        base_rest: PythonSource,
        head_rest: PythonSource,
        arriving: tuple[MovedDefinition, ...],
        leaving: tuple[MovedDefinition, ...],
        renames: RenameMap,
    ) -> bool:
        """
        :param base_rest: The module's base version, the definitions leaving taken out.
        :param head_rest: Its head version, the definitions arriving taken out.
        :param arriving: The definitions moving into it.
        :param leaving: The definitions moving out of it.
        :param renames: The renames the pull request makes throughout.
        :return: Whether each name only the head version imports is a definition that
            left it, or is bound as the module an arriving definition left binds it.
        """
        base_names = {
            binding.bound_name for binding in base_rest.imports(renames).bindings
        }
        for binding in head_rest.import_bindings.bindings:
            name = binding.bound_name
            if name in base_names:
                continue
            allowed = {
                definition.new_path for definition in leaving if definition.name == name
            }
            for definition in arriving:
                source = definition.source
                allowed |= source.imports(renames).sources_of(name)
                if name in source.defined_names:
                    allowed.add(
                        renames.renamed_identifier(f"{definition.source_module}.{name}")
                    )
            if binding.source not in allowed:
                return False
        return True

    def rest_changes(
        self,
        base_rest: PythonSource,
        head_rest: PythonSource,
        change: FileChange,
        context: JudgmentContext,
    ) -> ChangeKinds | None:
        """
        :param base_rest: The module's base version, the definitions leaving taken out.
        :param head_rest: Its head version, the definitions arriving taken out.
        :param change: The module's change.
        :param context: What the judgment may consult about the pull request.
        :return: What the change of the rest consists of, ``None`` when it is not
            provably mechanical; an added module may hold nothing else but imports
            and its docstring.
        """
        if change.base_text is None:
            statements = head_rest.tree.body
            documented = bool(statements) and PythonSource.is_documentation(
                statements[0]
            )
            only_imports = all(
                isinstance(statement, ast.Import | ast.ImportFrom)
                for statement in statements[documented:]
            )
            if not only_imports or head_rest.comments:
                return None
            return frozenset()
        kinds = self.comparison.source_changes(base_rest, head_rest, context)
        if kinds is None or kinds != {MechanicalChange.FORMATTING}:
            return kinds
        if base_rest.non_blank_lines == head_rest.non_blank_lines:
            return frozenset()
        return kinds
