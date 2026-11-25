"""
Judging one file's change: mechanical when a judgment proves it cannot alter what the
file does or says, otherwise in need of review.
"""

from __future__ import annotations

import difflib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from enum import StrEnum
from functools import cached_property
from pathlib import PurePosixPath

from basstler.class_property import classproperty
from basstler.git.commit_range import FileVersions
from basstler.review_triage.commit_tree import PACKAGE_INITIALIZER, CommitModules
from basstler.review_triage.docstring_examples import DocumentedExamples
from basstler.review_triage.member_renames import MemberRenamer
from basstler.review_triage.moved_definitions import MovedDefinitions
from basstler.review_triage.python_source import (
    ImportBindings,
    ImportSourceEquivalence,
    OwnerImports,
    PythonSource,
)
from basstler.review_triage.receiver_probes import RevealedReceivers
from basstler.review_triage.renames import RenameDecisions, RenameMap
from basstler.review_triage.rules import DEFAULT_RULES, TriageRule
from basstler.review_triage.definitions import DefinitionIndex

# %% what a mechanical change consists of


class ChangeKind(StrEnum):
    """
    The base of every enumeration of mechanical change kinds; an extension declares
    its own kinds by subclassing it.
    """

    @classproperty
    def no_change(cls) -> frozenset[ChangeKind]:
        """
        The kinds of change of two versions that are equal: none.
        """
        return frozenset()


ChangeKinds = frozenset[ChangeKind]
"""
The kinds of change one judgment found.
"""


class MechanicalChange(ChangeKind):
    """
    The kinds of mechanical change the built-in judgments find.
    """

    MOVE = "move"
    """
    The file was moved to another path.
    """

    IMPORTS = "imports"
    """
    Imports were added, removed or reordered, each name both versions import still bound
    to the same thing.
    """

    RENAME = "rename"
    """
    Identifiers the pull request renames throughout were replaced, in code, docstrings
    or comments.
    """

    FORMATTING = "formatting"
    """
    Only the layout of code, docstrings or comments changed.
    """

    EMPTY_PACKAGE = "empty package"
    """
    An empty package initializer was added, making its directory a package.
    """

    DEFINITIONS_MOVED_IN = "definitions moved in"
    """
    Definitions moved unchanged out of another module were added, with the imports
    they need and their section headers.
    """

    DEFINITIONS_MOVED_OUT = "definitions moved out"
    """
    Definitions another module now holds were removed, with their section headers.
    """

    SUBCLASS_SUBSTITUTED = "class replaced by subclass"
    """
    A class was replaced by a subclass the pull request adds, holding only members
    moved down from the class unchanged.
    """

    MODULE_DOCUMENTATION = "module documentation"
    """
    The documentation at the top of a module changed, which the module documentation
    rule counts as mechanical.
    """

    BASE_BRANCH_MERGE = "base branch merge"
    """
    Only merges of the base branch changed the file since the commit the triage starts
    from.
    """


# %% the verdict on one file


@dataclass(frozen=True)
class ReviewReason(ABC):
    """
    A part of a changed file that could not be shown to be mechanical.
    """

    line: int
    """
    The line of the head version it is on.
    """

    @property
    @abstractmethod
    def explanation(self) -> str:
        """
        What could not be shown, for a reviewer.
        """


class Difference(StrEnum):
    """
    A part of a file's change that no judgment proved mechanical.
    """

    ADDED_FILE = "the file is added"
    """
    The file is new, so there is no base version to compare it with.
    """

    DELETED_FILE = "the file is deleted"
    """
    The file is gone, so there is no head version to compare.
    """

    BINARY_FILE = "the file is binary"
    """
    Git compares the file as binary, which no judgment reads.
    """

    CODE_CHANGED = "the code here differs beyond the changes proven mechanical"
    """
    The code stops matching its base version here.
    """

    DOCSTRING_REWORDED = "the docstring is reworded beyond renames and reflowing"
    """
    A documentation string says something else.
    """

    COMMENT_REWORDED = "a comment is reworded beyond renames and reflowing"
    """
    A comment says something else.
    """

    TEXT_CHANGED = "no judgment proves the change from here on mechanical"
    """
    The first changed line of a file no judgment gave a narrower reason for.
    """


@dataclass(frozen=True)
class UnprovenDifference(ReviewReason):
    """
    A part of a file's change no judgment proved mechanical.
    """

    difference: Difference
    """
    Which part it is.
    """

    @property
    def explanation(self) -> str:
        return self.difference

    @classmethod
    def from_change(cls, change: FileVersions) -> UnprovenDifference:
        """
        :param change: A file needing review that no judgment gave a reason for.
        :return: Its first changed line, or the whole file when no judgment reads it.
        """
        if change.is_binary:
            return cls(1, Difference.BINARY_FILE)
        if change.base_text is None:
            return cls(1, Difference.ADDED_FILE)
        if change.head_text is None:
            return cls(1, Difference.DELETED_FILE)
        head_lines = change.head_text.splitlines()
        opcodes = difflib.SequenceMatcher(
            None, change.base_text.splitlines(), head_lines, autojunk=False
        ).get_opcodes()
        first = next((opcode for opcode in opcodes if opcode[0] != "equal"), None)
        head_start = 0 if first is None else first[3]
        return cls(min(head_start, len(head_lines) - 1) + 1, Difference.TEXT_CHANGED)


class ImportMismatch(StrEnum):
    """
    How the two versions of a file import a name differently.
    """

    ONLY_HEAD = "only the head version imports it, and not as a respelling"
    """
    The head binds a name the base did not, its code not shown to read it as before.
    """

    ONLY_BASE = "only the base version imports it, and not as a respelling"
    """
    The base bound a name the head no longer does, not shown to be unused or respelled.
    """

    SOURCE_CHANGED = "the versions import it from different sources"
    """
    Both bind the name, to objects not shown to be the same.
    """


@dataclass(frozen=True)
class ImportDifference(ReviewReason):
    """
    A name the two versions of a file import differently.
    """

    bound_name: str
    """
    The name the import binds.
    """

    mismatch: ImportMismatch
    """
    How the versions import it differently.
    """

    @property
    def explanation(self) -> str:
        return f"`{self.bound_name}` - {self.mismatch}"


@dataclass(frozen=True)
class FileVerdict(ABC):
    """
    The verdict on one changed file.
    """

    change: FileVersions
    """
    The change judged.
    """


@dataclass(frozen=True)
class MechanicalFile(FileVerdict):
    """
    A file whose change is provably mechanical, so a reviewer need not read it.
    """

    kinds: frozenset[ChangeKind] = ChangeKind.no_change
    """
    What the change consists of.
    """


@dataclass(frozen=True)
class FileNeedingReview(FileVerdict):
    """
    A file whose change could not be shown to be mechanical.
    """

    reasons: tuple[ReviewReason, ...] = field(default=(), compare=False)
    """
    The parts of the change a judgment tried and failed to show mechanical.
    """


# %% judgments


class FileSuffix(StrEnum):
    """
    The file name suffixes the built-in comparisons read.
    """

    MARKDOWN = ".md"
    """
    Markdown documentation.
    """

    RESTRUCTURED_TEXT = ".rst"
    """
    reStructuredText documentation.
    """

    TEXT = ".txt"
    """
    Plain text.
    """

    PYTHON = ".py"
    """
    Python source.
    """

    PYTHON_STUB = ".pyi"
    """
    A Python stub, holding type hints only.
    """


@dataclass(frozen=True)
class JudgmentContext:
    """
    What a judgment may consult about the pull request beyond the file it judges.
    """

    renames: RenameMap = RenameMap()
    """
    The renames the pull request makes throughout.
    """

    base_definitions: DefinitionIndex = field(default_factory=DefinitionIndex)
    """
    The functions, methods and classes the base commit defines.
    """

    moved_definitions: MovedDefinitions = MovedDefinitions()
    """
    The definitions the pull request moves between modules.
    """

    substitutions: RenameMap = RenameMap()
    """
    Classes a file may replace by a subclass the pull request adds, as renames.
    """

    rules: frozenset[TriageRule] = DEFAULT_RULES
    """
    The rules in force.
    """

    member_renamer: MemberRenamer | None = None
    """
    Renames the occurrences of the module members the pull request renames that are
    proven to refer to them; ``None`` when it renames none.
    """

    optional_prose_renames: RenameMap = RenameMap()
    """
    Renames the prose of the file being judged may make or leave out, each docstring
    and the comments on their own.
    """

    owner_imports: OwnerImports = OwnerImports()
    """
    The imports the file being judged gains and may lose for the moves its base
    version was renamed for.
    """

    review_reasons: list[ReviewReason] = field(
        default_factory=list, compare=False, hash=False, repr=False, kw_only=True
    )
    """
    The reasons for review the judgments of the file being judged found so far.
    """

    head_definitions: DefinitionIndex = field(
        default_factory=DefinitionIndex, kw_only=True
    )
    """
    The functions, methods and classes the head commit defines.
    """

    base_modules: CommitModules | None = field(default=None, kw_only=True)
    """
    The base commit's modules, which say the package each version of a file is in;
    ``None`` leaves that to the directories holding the file.
    """

    head_modules: CommitModules | None = field(default=None, kw_only=True)
    """
    The head commit's modules, as :attr:`base_modules`.
    """

    import_source_equivalence: ImportSourceEquivalence = field(
        default_factory=ImportSourceEquivalence, kw_only=True
    )
    """
    Decides whether an import the file being judged respells still binds its object.
    """

    revealed_receivers: RevealedReceivers | None = field(default=None, kw_only=True)
    """
    The classes a type checker reveals for the pull request's receivers, ``None``
    without a type checker.
    """

    def renamed_imports(self, base: PythonSource, head: PythonSource) -> ImportBindings:
        """
        :param base: The base version of the file being judged.
        :param head: Its head version.
        :return: The names the base version's imports bind once renamed, with the
            imports it gains and may lose for its renames applied.
        """
        return self.owner_imports.applied_to(
            base.imports(self.renames), head.import_bindings
        )

    @staticmethod
    def package_of(
        modules: CommitModules | None, path: PurePosixPath
    ) -> tuple[str, ...]:
        """
        :param modules: The modules of the commit holding the file, if known.
        :param path: The file's path.
        :return: The package its relative imports start from.
        """
        if modules is None:
            return path.parent.parts
        return modules.package(path)

    @cached_property
    def substituted(self) -> JudgmentContext:
        """
        This context with :attr:`substitutions` applied as renames.
        """
        return replace(
            self,
            renames=RenameMap.from_decisions(
                [
                    RenameDecisions(self.renames.renames),
                    RenameDecisions(self.substitutions.renames),
                ]
            ),
            substitutions=RenameMap(),
        )


class FileJudgment(ABC):
    """
    Decides whether the change of the files it applies to is mechanical.
    """

    @abstractmethod
    def applies_to(self, change: FileVersions) -> bool:
        """
        :param change: A file the pull request changes.
        :return: Whether this judgment decides it.
        """

    @abstractmethod
    def changes(
        self, change: FileVersions, context: JudgmentContext
    ) -> ChangeKinds | None:
        """
        :param change: A file this judgment applies to.
        :param context: What the judgment may consult about the pull request.
        :return: What the change consists of, ``None`` when it is not provably
            mechanical.
        """


class ContentComparison(FileJudgment, ABC):
    """
    Compares both text versions of the files whose name has one of its suffixes.
    """

    @classproperty
    @abstractmethod
    def suffixes(cls) -> frozenset[str]:
        """
        The file name suffixes of the files this comparison reads, a :class:`FileSuffix`
        member each for a built-in comparison.
        """

    @abstractmethod
    def text_changes(
        self, base_text: str, head_text: str, context: JudgmentContext
    ) -> ChangeKinds | None:
        """
        :param base_text: The file's content in the base commit.
        :param head_text: The file's content in the head commit.
        :param context: What the judgment may consult about the pull request.
        :return: What the change consists of, ``None`` when it is not provably
            mechanical.
        """

    def applies_to(self, change: FileVersions) -> bool:
        return (
            change.base_text is not None
            and change.head_text is not None
            and change.path.suffix in self.suffixes
        )

    def changes(
        self, change: FileVersions, context: JudgmentContext
    ) -> ChangeKinds | None:
        return self.text_changes(change.base_text, change.head_text, context)


class ProseComparison(ContentComparison):
    """
    Compares prose: documentation files, docstrings and comments.
    """

    @classproperty
    def suffixes(cls) -> frozenset[str]:
        return frozenset(
            {FileSuffix.MARKDOWN, FileSuffix.RESTRUCTURED_TEXT, FileSuffix.TEXT}
        )

    def text_changes(
        self, base_text: str, head_text: str, context: JudgmentContext
    ) -> ChangeKinds | None:
        if base_text == head_text:
            return ChangeKind.no_change
        renamed = context.renames.renamed_prose(base_text)
        candidates = tuple(
            dict.fromkeys(
                (renamed, context.optional_prose_renames.renamed_prose(renamed))
            )
        )
        if head_text in candidates:
            return frozenset({MechanicalChange.RENAME})
        if base_text.split() == head_text.split():
            return frozenset({MechanicalChange.FORMATTING})
        if head_text.split() in [candidate.split() for candidate in candidates]:
            return frozenset({MechanicalChange.RENAME, MechanicalChange.FORMATTING})
        return None


@dataclass(frozen=True)
class PythonComparison(ContentComparison):
    """
    Compares Python files by their syntax trees, their imports, their docstrings and
    their comments.
    """

    prose: ProseComparison = field(default_factory=ProseComparison)
    """
    How the docstrings and comments are compared.
    """

    @classproperty
    def suffixes(cls) -> frozenset[str]:
        return frozenset({FileSuffix.PYTHON, FileSuffix.PYTHON_STUB})

    def text_changes(
        self, base_text: str, head_text: str, context: JudgmentContext
    ) -> ChangeKinds | None:
        return self.source_changes(
            PythonSource.from_text(base_text),
            PythonSource.from_text(head_text),
            context,
        )

    def changes(
        self, change: FileVersions, context: JudgmentContext
    ) -> ChangeKinds | None:
        """
        :meth:`ContentComparison.changes`, resolving each version's relative imports
        against the directory holding it; a name only one version imports needs review
        unless its code uses it and both versions star-import it from one module, or
        only the head imports it, as an identity decorator of the base commit.
        """
        base_path = change.previous_path or change.path
        base = PythonSource.from_text(
            change.base_text, context.package_of(context.base_modules, base_path)
        )
        head = PythonSource.from_text(
            change.head_text, context.package_of(context.head_modules, change.path)
        )
        kinds = self.source_changes(base, head, context)
        if kinds is None or MechanicalChange.IMPORTS not in kinds:
            return kinds
        base_imports = context.renamed_imports(base, head)
        head_imports = ImportBindings(
            frozenset(
                binding
                for binding in head.import_bindings.bindings
                if binding.bound_name in base_imports.bound_names
                or binding.bound_name not in head.decorator_only_names
                or not context.base_definitions.is_identity(binding.member_name)
            )
        )
        unexplained = [
            *(
                ImportDifference(
                    head.import_line(binding.bound_name),
                    binding.bound_name,
                    ImportMismatch.ONLY_BASE,
                )
                for binding in base_imports.unexplained_bindings(
                    head_imports, base.referenced_names(context.renames)
                )
            ),
            *(
                ImportDifference(
                    head.import_line(binding.bound_name),
                    binding.bound_name,
                    ImportMismatch.ONLY_HEAD,
                )
                for binding in head_imports.unexplained_bindings(
                    base_imports, head.referenced_names(RenameMap())
                )
            ),
        ]
        if unexplained:
            context.review_reasons.extend(unexplained)
            return None
        return kinds

    def source_changes(
        self, base: PythonSource, head: PythonSource, context: JudgmentContext
    ) -> ChangeKinds | None:
        """
        :param base: The file's base version.
        :param head: The file's head version.
        :param context: What the judgment may consult about the pull request.
        :return: What the change consists of, ``None`` when it is not provably
            mechanical, as for a version that is not valid Python.
        """
        if not (base.parses and head.parses):
            return None
        skips_module_documentation = TriageRule.MODULE_DOCUMENTATION in context.rules
        if skips_module_documentation:
            kinds = self.compared_changes(
                base.without_module_documentation,
                head.without_module_documentation,
                context,
            )
        else:
            kinds = self.compared_changes(base, head, context)
        if kinds is None:
            return None
        kinds = set(kinds)
        if (
            skips_module_documentation
            and base.module_documentation != head.module_documentation
        ):
            kinds.add(MechanicalChange.MODULE_DOCUMENTATION)
        if not kinds and base.text != head.text:
            kinds.add(MechanicalChange.FORMATTING)
        return frozenset(kinds)

    def compared_changes(
        self, base: PythonSource, head: PythonSource, context: JudgmentContext
    ) -> ChangeKinds | None:
        """
        :param base: The file's base version.
        :param head: The file's head version.
        :param context: What the judgment may consult about the pull request.
        :return: What the change consists of, formatting of the whole file aside,
            ``None`` when it is not provably mechanical.
        """
        code_kinds = self.code_changes(base, head, context)
        if code_kinds is None:
            return None
        kinds = set(code_kinds)
        if base.import_statements != head.import_statements:
            disagreeing = context.renamed_imports(base, head).disagreeing_names(
                head.import_bindings, context.import_source_equivalence
            )
            if disagreeing:
                context.review_reasons.extend(
                    ImportDifference(
                        head.import_line(name), name, ImportMismatch.SOURCE_CHANGED
                    )
                    for name in disagreeing
                )
                return None
            kinds.add(MechanicalChange.IMPORTS)
        for base_documentation, statement in zip(
            base.documentation, head.documentation_statements, strict=True
        ):
            documentation_kinds = self.documentation_changes(
                base_documentation, statement.value.value, statement.lineno, context
            )
            if documentation_kinds is None:
                return None
            kinds |= documentation_kinds
        comment_kinds = self.prose.text_changes(base.comments, head.comments, context)
        if comment_kinds is None:
            context.review_reasons.append(
                UnprovenDifference(
                    head.first_comment_line_differing_from(base),
                    Difference.COMMENT_REWORDED,
                )
            )
            return None
        kinds |= comment_kinds
        return frozenset(kinds)

    def documentation_changes(
        self,
        base_documentation: str,
        head_documentation: str,
        head_line: int,
        context: JudgmentContext,
    ) -> ChangeKinds | None:
        """
        :param base_documentation: A docstring of the base version.
        :param head_documentation: The docstring in its place in the head version.
        :param head_line: The head line the docstring starts on.
        :param context: What the judgment may consult, collecting the reasons for review.
        :return: What the docstring's change consists of, its python examples judged
            as code, ``None`` when it is not provably mechanical.
        """
        base_split = DocumentedExamples.from_docstring(base_documentation)
        head_split = DocumentedExamples.from_docstring(head_documentation)
        if len(base_split.examples) != len(head_split.examples):
            base_split = DocumentedExamples(base_documentation, ())
            head_split = DocumentedExamples(head_documentation, ())
        kinds = self.prose.text_changes(base_split.prose, head_split.prose, context)
        if kinds is None:
            context.review_reasons.append(
                UnprovenDifference(head_line, Difference.DOCSTRING_REWORDED)
            )
            return None
        kinds = set(kinds)
        for base_example, head_example in zip(
            base_split.examples, head_split.examples, strict=True
        ):
            if base_example.code == head_example.code:
                continue
            example_context = replace(context, review_reasons=[])
            example_kinds = self.source_changes(
                PythonSource.from_text(base_example.code),
                PythonSource.from_text(head_example.code),
                example_context,
            )
            if example_kinds is None:
                example_line = head_line + head_example.first_line
                context.review_reasons.extend(
                    replace(reason, line=example_line + reason.line - 1)
                    for reason in example_context.review_reasons
                    or [UnprovenDifference(1, Difference.CODE_CHANGED)]
                )
                return None
            kinds |= example_kinds
        return frozenset(kinds)

    def code_changes(
        self, base: PythonSource, head: PythonSource, context: JudgmentContext
    ) -> ChangeKinds | None:
        """
        :param base: The file's base version.
        :param head: The file's head version.
        :param context: What the judgment may consult about the pull request.
        :return: What the change of the code, imports and docstrings aside, consists
            of, ``None`` when it is not provably mechanical.
        """
        head_code = head.code(RenameMap())
        if base.code(RenameMap()) == head_code:
            return ChangeKind.no_change
        if base.code(context.renames) == head_code:
            return frozenset({MechanicalChange.RENAME})
        return None


class EmptyPackageAddition(FileJudgment):
    """
    Judges an added package initializer holding nothing but whitespace as mechanical.
    """

    def applies_to(self, change: FileVersions) -> bool:
        return (
            change.base_text is None
            and change.head_text is not None
            and change.path.name == PACKAGE_INITIALIZER
        )

    def changes(
        self, change: FileVersions, context: JudgmentContext
    ) -> ChangeKinds | None:
        if change.head_text.strip():
            return None
        return frozenset({MechanicalChange.EMPTY_PACKAGE})


class RenamedTextComparison(FileJudgment):
    """
    Judges a text file of any other type: mechanical only when the renames alone turn
    its base version into its head version, since its whitespace may carry meaning.
    """

    def applies_to(self, change: FileVersions) -> bool:
        return change.base_text is not None and change.head_text is not None

    def changes(
        self, change: FileVersions, context: JudgmentContext
    ) -> ChangeKinds | None:
        if context.renames.renamed_prose(change.base_text) == change.head_text:
            return frozenset({MechanicalChange.RENAME})
        return None


# %% judging a file


@dataclass(frozen=True)
class FileTriager:
    """
    Judges each changed file by the first judgment that applies to it; a file no
    judgment applies to is mechanical only when its content is unchanged.
    """

    context: JudgmentContext
    """
    What the judgments may consult about the pull request.
    """

    judgments: tuple[FileJudgment, ...] = (
        PythonComparison(),
        ProseComparison(),
        EmptyPackageAddition(),
        RenamedTextComparison(),
    )
    """
    The judgments, tried in order.
    """

    def triage(self, change: FileVersions) -> FileVerdict:
        """
        :param change: A file the pull request changes.
        :return: Whether a reviewer has to read it, with the reasons of the judgment
            that renamed its members when that judgment gave any, else of the others,
            else its first changed line.
        """
        member_renamed_context = replace(self.context, review_reasons=[])
        context = replace(self.context, review_reasons=[])
        kinds = self.member_renamed_changes(change, member_renamed_context)
        if kinds is None:
            kinds = self.judged_changes(change, context)
        if change.previous_path is not None and kinds is not None:
            kinds |= {MechanicalChange.MOVE}
        if not kinds:
            reasons = member_renamed_context.review_reasons or context.review_reasons
            return FileNeedingReview(
                change,
                tuple(dict.fromkeys(reasons))
                or (UnprovenDifference.from_change(change),),
            )
        return MechanicalFile(change, kinds)

    def triage_each(self, changes: tuple[FileVersions, ...]) -> tuple[FileVerdict, ...]:
        """
        :param changes: Files the pull request changes.
        :return: :meth:`triage` of each, in their order.
        """
        return tuple(self.triage(change) for change in changes)

    def member_renamed_changes(
        self, change: FileVersions, context: JudgmentContext
    ) -> frozenset[ChangeKind] | None:
        """
        :param change: A file the pull request changes.
        :param context: What the judgments may consult, collecting this file's reasons
            for review.
        :return: What its content change consists of once the occurrences in its code,
            or in a Markdown file's python code blocks, proven to refer to a renamed
            member are renamed in its base version, ``None`` when none is or the
            change is not then provably mechanical.
        """
        renamer = context.member_renamer
        if renamer is None or change.base_text is None or change.head_text is None:
            return None
        if change.path.suffix == FileSuffix.MARKDOWN:
            renamed = renamer.renamed_documentation(change)
        elif PythonComparison().applies_to(change):
            renamed = renamer.renamed_base(change)
        else:
            return None
        if renamed.text == change.base_text:
            return None
        kinds = self.judged_changes(
            replace(change, base_text=renamed.text),
            replace(
                context,
                optional_prose_renames=renamed.prose_renames,
                owner_imports=renamed.owner_imports,
            ),
        )
        return None if kinds is None else kinds | {MechanicalChange.RENAME}

    def judged_changes(
        self, change: FileVersions, context: JudgmentContext
    ) -> frozenset[ChangeKind] | None:
        """
        :param change: A file the pull request changes.
        :param context: What the judgments may consult, collecting this file's reasons
            for review.
        :return: What its content change consists of, ``None`` when it is not
            provably mechanical.
        """
        if change.head_text is not None and change.base_text == change.head_text:
            return ChangeKind.no_change
        judgment = next(
            (judgment for judgment in self.judgments if judgment.applies_to(change)),
            None,
        )
        if judgment is None:
            return None
        kinds = judgment.changes(change, context)
        substituted_class = context.substitutions.word_pattern
        if (
            kinds is not None
            or substituted_class is None
            or not substituted_class.search(change.base_text or "")
        ):
            return kinds
        substituted = judgment.changes(change, context.substituted)
        if substituted is None:
            return None
        return substituted - {MechanicalChange.RENAME} | {
            MechanicalChange.SUBCLASS_SUBSTITUTED
        }
