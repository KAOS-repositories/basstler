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
    FileVersions,
    FileJudgment,
    JudgmentContext,
    MechanicalChange,
    PythonComparison,
)
from basstler.review_triage.definition_succession import DefinitionSuccession
from basstler.review_triage.detection import RenameDetection
from basstler.review_triage.keyword_arguments import KeywordArgumentComparison
from basstler.review_triage.moved_definitions import MovedDefinition, MovedDefinitions
from basstler.github.pull_request_changes import PullRequestChanges
from basstler.review_triage.python_source import LineSpan, PythonSource
from basstler.review_triage.rename_sources import RenameSource
from basstler.review_triage.renames import (
    DOTTED_NAME_SEPARATOR,
    MemberRename,
    Rename,
    RenameCandidates,
    RenameDecisions,
    RenameMap,
)

# %% one definition of a module


@dataclass(frozen=True)
class ModuleDefinition:
    """
    A top-level definition one version of a module makes.
    """

    module: str
    """
    The module's dotted path.
    """

    name: str
    """
    The name the module defines it by.
    """

    module_source: PythonSource
    """
    The version of the module making it.
    """

    @property
    def dotted_path(self) -> str:
        """
        Its dotted path.
        """
        return f"{self.module}{DOTTED_NAME_SEPARATOR}{self.name}"

    @property
    def code(self) -> PythonSource:
        """
        Its statement alone.
        """
        source = self.module_source
        return PythonSource.from_text(
            source.lines_of(source.definition_span(self.name))
        )

    def sole_namesake(
        self, gained: dict[str, list[ModuleDefinition]]
    ) -> ModuleDefinition | None:
        """
        :param gained: The definitions modules newly make, by name.
        :return: The one among them of its name, ``None`` when there is none or more.
        """
        namesakes = gained.get(self.name, [])
        if len(namesakes) != 1:
            return None
        return namesakes[0]


# %% detection


class DefinitionMoveDetection(RenameSource):
    """
    Detects a top-level definition that leaves a module the head commit keeps for
    another module, as a rename of its dotted path, unless the code of another added
    definition carries it on.
    """

    @classproperty
    def label(cls) -> str:
        return "definition move"

    def decisions(self, changes: PullRequestChanges) -> RenameDecisions:
        base = CommitModules(changes.commits.base_tree)
        head = CommitModules(changes.commits.head_tree)
        modules = [
            change
            for change in changes.files
            if change.path.suffix == MODULE_SUFFIX
            and PythonSource.every_version_parses(change)
        ]
        succession = DefinitionSuccession.from_changes(changes)
        gained: dict[str, list[ModuleDefinition]] = {}
        for change in modules:
            for name in self.added_names(change):
                gained.setdefault(name, []).append(
                    ModuleDefinition(
                        head.module_path(change.path),
                        name,
                        PythonSource.from_text(change.head_text),
                    )
                )
        removed = [
            ModuleDefinition(old_module, name, PythonSource.from_text(change.base_text))
            for change in modules
            for old_module, name in self.removed_names(change, base)
            if DOTTED_NAME_SEPARATOR in old_module
        ]
        renames: list[Rename] = [
            Rename(definition.dotted_path, namesake.dotted_path, self)
            for definition in removed
            if (namesake := definition.sole_namesake(gained)) is not None
            and succession.is_uncontested(definition.dotted_path, namesake.dotted_path)
        ]
        renames.extend(self.renamed_moves(changes, removed, gained, succession))
        return RenameDecisions(tuple(sorted(renames, key=lambda rename: rename.old)))

    def renamed_moves(
        self,
        changes: PullRequestChanges,
        removed: list[ModuleDefinition],
        gained: dict[str, list[ModuleDefinition]],
        succession: DefinitionSuccession,
    ) -> Iterator[MemberRename]:
        """
        :param changes: A pull request and the files it changes.
        :param removed: The definitions modules the head commit keeps no longer make.
        :param gained: The definitions modules newly make, by name.
        :param succession: Which added definition carries on each removed one.
        :return: The moves of a definition to another module under a new name, where
            its successor's code and the substitutions of the diff, or of the code of
            the definitions moving under their own name, both say so.
        """
        candidates = RenameCandidates()
        for change in changes.files:
            if PythonComparison().applies_to(change):
                RenameDetection.collect(
                    PythonSource.from_text(change.base_text),
                    PythonSource.from_text(change.head_text),
                    candidates,
                )
        for definition in removed:
            namesake = definition.sole_namesake(gained)
            if namesake is not None:
                RenameDetection.collect(definition.code, namesake.code, candidates)
        names = candidates.dominant_pairs(
            frozenset(definition.name for definition in removed), frozenset(gained)
        )
        for definition in removed:
            new = succession.successors.get(definition.dotted_path)
            if new is None:
                continue
            new_module, _, new_name = new.rpartition(DOTTED_NAME_SEPARATOR)
            if (
                new_module != definition.module
                and names.get(definition.name) == new_name
            ):
                yield MemberRename(definition.dotted_path, new, self)

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
            if change.path.suffix == MODULE_SUFFIX
            and change.head_text is not None
            and PythonSource.every_version_parses(change)
        ]
        sources: dict[str, list[FileVersions]] = {}
        targets: dict[str, list[FileVersions]] = {}
        for change in modules:
            if change.base_text is not None:
                module = base.module_path(change.previous_path or change.path)
                sources.setdefault(module, []).append(change)
            targets.setdefault(head.module_path(change.path), []).append(change)
        moved = []
        for rename in renames.renames:
            if not isinstance(rename.found_by, DefinitionMoveDetection):
                continue
            old_module, _, old_name = rename.old.rpartition(DOTTED_NAME_SEPARATOR)
            new_module, _, new_name = rename.new.rpartition(DOTTED_NAME_SEPARATOR)
            source = next(
                (
                    candidate
                    for candidate in sources.get(old_module, [])
                    if old_name
                    in PythonSource.from_text(candidate.base_text).defined_names
                ),
                None,
            )
            target = next(
                (
                    candidate
                    for candidate in targets.get(new_module, [])
                    if new_name
                    in PythonSource.from_text(candidate.head_text).defined_names
                ),
                None,
            )
            if source is None or target is None:
                continue
            moved.append(
                MovedDefinition(
                    source.previous_path or source.path,
                    source.base_text,
                    base.package(source.previous_path or source.path),
                    target.path,
                    rename.old,
                    rename.new,
                )
            )
        return MovedDefinitions(tuple(moved))

    @staticmethod
    def added_names(change: FileVersions) -> frozenset[str]:
        """
        :param change: A changed module.
        :return: The names its head version defines and its base version did not.
        """
        if change.head_text is None:
            return frozenset()
        head_names = PythonSource.from_text(change.head_text).defined_names
        if change.base_text is None:
            return head_names
        return head_names - PythonSource.from_text(change.base_text).defined_names

    @staticmethod
    def removed_names(
        change: FileVersions, base: CommitModules
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
            PythonSource.from_text(change.base_text).defined_names
            - PythonSource.from_text(change.head_text).defined_names
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

    def applies_to(self, change: FileVersions) -> bool:
        return self.comparison.applies_to(change) or (
            change.base_text is None
            and change.head_text is not None
            and change.path.suffix == MODULE_SUFFIX
            and change.path.name != PACKAGE_INITIALIZER
        )

    def changes(
        self, change: FileVersions, context: JudgmentContext
    ) -> ChangeKinds | None:
        base_path = change.previous_path or change.path
        arriving = context.moved_definitions.arriving_at(change.path)
        leaving = context.moved_definitions.leaving(base_path)
        if not arriving and not leaving:
            if change.base_text is None:
                return None
            return self.comparison.changes(change, context)
        head = PythonSource.from_text(
            change.head_text, context.package_of(context.head_modules, change.path)
        )
        base = PythonSource.from_text(
            change.base_text or "",
            context.package_of(context.base_modules, base_path),
        )
        head_rest = head.without(
            self.spans(head, [definition.new_name for definition in arriving], base)
        )
        base_rest = base.without(
            self.spans(base, [definition.name_in(base) for definition in leaving], head)
        )
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
        source: PythonSource, names: list[str], other_version: PythonSource
    ) -> tuple[LineSpan, ...]:
        """
        :param source: One version of a module.
        :param names: The names of definitions it holds that the other version does
            not.
        :param other_version: The module's other version.
        :return: The definitions' lines, with the section header right above each
            when the other version lacks it.
        """
        spans = tuple(source.definition_span(name) for name in names)
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
            source = self.renamed_source(definition, context)
            definition_kinds = self.comparison.text_changes(
                source.lines_of(source.definition_span(definition.name_in(source))),
                head.lines_of(head.definition_span(definition.new_name)),
                context,
            )
            if definition_kinds is None:
                return None
            kinds |= definition_kinds
            if source.text != definition.source_text:
                kinds.add(MechanicalChange.RENAME)
        return frozenset(kinds)

    @staticmethod
    def renamed_source(
        definition: MovedDefinition, context: JudgmentContext
    ) -> PythonSource:
        """
        :param definition: A moved definition.
        :param context: What the judgment may consult about the pull request.
        :return: The base version of the module it left, the occurrences proven to
            refer to a renamed member renamed.
        """
        renamer = context.member_renamer
        if renamer is None:
            return definition.source
        renamed = renamer.renamed_code(
            definition.source_text,
            definition.source_text,
            definition.source_module,
            definition.source_path.name == PACKAGE_INITIALIZER,
        )
        return PythonSource.from_text(renamed.text, definition.source_package)

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
            left it, or is bound as the module an arriving definition left binds it,
            or names where a definition of that module moved under a new name.
        """
        base_names = {
            binding.bound_name for binding in base_rest.imports(renames).bindings
        }
        for binding in head_rest.import_bindings.bindings:
            name = binding.bound_name
            if name in base_names:
                continue
            allowed = {
                definition.new_path
                for definition in leaving
                if definition.new_name == name
            }
            for definition in arriving:
                source = definition.source
                allowed |= source.imports(renames).sources_of(name)
                allowed |= {
                    renamed
                    for defined in source.defined_names
                    if (
                        renamed := renames.renamed_identifier(
                            f"{definition.source_module}.{defined}"
                        )
                    ).rpartition(DOTTED_NAME_SEPARATOR)[2]
                    == name
                }
            if binding.source not in allowed:
                return False
        return True

    def rest_changes(
        self,
        base_rest: PythonSource,
        head_rest: PythonSource,
        change: FileVersions,
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
