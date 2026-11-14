"""
Judging one file's change: mechanical when a judgment proves it cannot alter what the
file does or says, otherwise in need of review.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from enum import StrEnum
from functools import cached_property

from basstler.class_property import classproperty
from basstler.git.commit_range import FileChange
from basstler.review_triage.commit_tree import PACKAGE_INITIALIZER
from basstler.review_triage.moved_definitions import MovedDefinitions
from basstler.review_triage.python_source import PythonSource
from basstler.review_triage.renames import RenameDecisions, RenameMap
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


# %% the verdict on one file


@dataclass(frozen=True)
class FileVerdict(ABC):
    """
    The verdict on one changed file.
    """

    change: FileChange
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
    def applies_to(self, change: FileChange) -> bool:
        """
        :param change: A file the pull request changes.
        :return: Whether this judgment decides it.
        """

    @abstractmethod
    def changes(
        self, change: FileChange, context: JudgmentContext
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

    def applies_to(self, change: FileChange) -> bool:
        return (
            change.base_text is not None
            and change.head_text is not None
            and change.path.suffix in self.suffixes
        )

    def changes(
        self, change: FileChange, context: JudgmentContext
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
        if renamed == head_text:
            return frozenset({MechanicalChange.RENAME})
        if base_text.split() == head_text.split():
            return frozenset({MechanicalChange.FORMATTING})
        if renamed.split() == head_text.split():
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
            PythonSource(base_text), PythonSource(head_text), context
        )

    def changes(
        self, change: FileChange, context: JudgmentContext
    ) -> ChangeKinds | None:
        """
        :meth:`ContentComparison.changes`, resolving each version's relative imports
        against the directory holding it.
        """
        base_path = change.previous_path or change.path
        return self.source_changes(
            PythonSource(change.base_text, base_path.parent.parts),
            PythonSource(change.head_text, change.path.parent.parts),
            context,
        )

    def source_changes(
        self, base: PythonSource, head: PythonSource, context: JudgmentContext
    ) -> ChangeKinds | None:
        """
        :param base: The file's base version.
        :param head: The file's head version.
        :param context: What the judgment may consult about the pull request.
        :return: What the change consists of, ``None`` when it is not provably
            mechanical.
        """
        code_kinds = self.code_changes(base, head, context)
        if code_kinds is None:
            return None
        kinds = set(code_kinds)
        if base.import_statements != head.import_statements:
            if not base.imports(context.renames).agrees_with(head.import_bindings):
                return None
            kinds.add(MechanicalChange.IMPORTS)
        prose_pairs = [
            *zip(base.documentation, head.documentation, strict=True),
            (base.comments, head.comments),
        ]
        for base_prose, head_prose in prose_pairs:
            prose_kinds = self.prose.text_changes(base_prose, head_prose, context)
            if prose_kinds is None:
                return None
            kinds |= prose_kinds
        if not kinds and base.text != head.text:
            kinds.add(MechanicalChange.FORMATTING)
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

    def applies_to(self, change: FileChange) -> bool:
        return (
            change.base_text is None
            and change.head_text is not None
            and change.path.name == PACKAGE_INITIALIZER
        )

    def changes(
        self, change: FileChange, context: JudgmentContext
    ) -> ChangeKinds | None:
        if change.head_text.strip():
            return None
        return frozenset({MechanicalChange.EMPTY_PACKAGE})


class RenamedTextComparison(FileJudgment):
    """
    Judges a text file of any other type: mechanical only when the renames alone turn
    its base version into its head version, since its whitespace may carry meaning.
    """

    def applies_to(self, change: FileChange) -> bool:
        return change.base_text is not None and change.head_text is not None

    def changes(
        self, change: FileChange, context: JudgmentContext
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

    def triage(self, change: FileChange) -> FileVerdict:
        """
        :param change: A file the pull request changes.
        :return: Whether a reviewer has to read it.
        """
        kinds = self.judged_changes(change)
        if change.previous_path is not None and kinds is not None:
            kinds |= {MechanicalChange.MOVE}
        if not kinds:
            return FileNeedingReview(change)
        return MechanicalFile(change, kinds)

    def judged_changes(self, change: FileChange) -> frozenset[ChangeKind] | None:
        """
        :param change: A file the pull request changes.
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
        kinds = judgment.changes(change, self.context)
        substituted_class = self.context.substitutions.word_pattern
        if (
            kinds is not None
            or substituted_class is None
            or not substituted_class.search(change.base_text or "")
        ):
            return kinds
        substituted = judgment.changes(change, self.context.substituted)
        if substituted is None:
            return None
        return substituted - {MechanicalChange.RENAME} | {
            MechanicalChange.SUBCLASS_SUBSTITUTED
        }
