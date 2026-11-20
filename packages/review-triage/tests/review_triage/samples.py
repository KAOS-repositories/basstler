"""
The file versions and pull requests the review triage suites read.
"""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any

from basstler.class_property import classproperty
from basstler.git.commit_range import FileVersions
from basstler.review_triage.definitions import DefinitionIndex, SourceDefinitions

from basstler_testing.constants.paths import DatasetLocation
from basstler.text_file import TextFile

# %% one file in two versions


class FileSample(StrEnum):
    """
    A file in a base and a head version, by the directory holding both.
    """

    BEHAVIOUR_CHANGED = "behaviour-changed"
    CODE_REFORMATTED = "code-reformatted"
    DOCSTRING_REFLOWED = "docstring-reflowed"
    DOCSTRING_REWORDED = "docstring-reworded"
    DOCUMENTATION_IMPORT_MOVED = "documentation-import-moved"
    DOCUMENTATION_REFLOWED = "documentation-reflowed"
    DOCUMENTATION_RENAMED = "documentation-renamed"
    IDENTIFIER_RENAMED = "identifier-renamed"
    IDENTITY_DECORATOR_ADDED = "identity-decorator-added"
    IMPORT_ADDED_FROM_OTHER_MODULE = "import-added-from-other-module"
    IMPORT_ADDED_UNDER_STAR_IMPORT = "import-added-under-star-import"
    IMPORT_ADDED_UNUSED = "import-added-unused"
    IMPORT_REMOVED_UNUSED = "import-removed-unused"
    IMPORT_SOURCE_CHANGED = "import-source-changed"
    IMPORTS_REORDERED = "imports-reordered"
    KEYWORD_ARGUMENTS_ADDED = "keyword-arguments-added"
    KEYWORD_ARGUMENTS_REORDERED = "keyword-arguments-reordered"
    KEYWORD_ARGUMENTS_SWAPPED = "keyword-arguments-swapped"
    KEYWORD_ARGUMENTS_UNKNOWN_CALLEE = "keyword-arguments-unknown-callee"
    KEYWORD_ONLY_PARAMETERS = "keyword-only-parameters"
    MODULE_DOCUMENTATION_AND_CODE_CHANGED = "module-documentation-and-code-changed"
    MODULE_DOCUMENTATION_REWORDED = "module-documentation-reworded"
    RECEIVER_BINDS_DIFFERENTLY = "receiver-binds-differently"
    RECEIVER_TYPE_AMBIGUOUS = "receiver-type-ambiguous"
    RECEIVER_TYPE_FOLLOWED = "receiver-type-followed"
    RECEIVER_TYPE_INFERRED = "receiver-type-inferred"
    RECEIVER_TYPE_UNKNOWN = "receiver-type-unknown"
    RELATIVE_IMPORT_MOVED = "relative-import-moved"
    STRING_LITERAL_RENAMED = "string-literal-renamed"
    TEMPLATE_RENAMED = "template-renamed"
    UTF_8_AND_TREE_REMOVAL_FIXES = "utf-8-and-tree-removal-fixes"
    UTF_8_FIX_AND_CODE_CHANGED = "utf-8-fix-and-code-changed"
    UTF_8_FIX_PARTIAL = "utf-8-fix-partial"
    UTF_8_FIX_REFORMATTED = "utf-8-fix-reformatted"

    @property
    def directory(self) -> Path:
        """
        The directory holding both versions.
        """
        return DatasetLocation.REVIEW_TRIAGE / self

    def change(self) -> FileVersions:
        """
        :return: The change from the base to the head version, at a path with their
            suffix.
        """
        base = next(self.directory.glob("base.*"))
        head = next(self.directory.glob("head.*"))
        return FileVersions(
            PurePosixPath(f"sample{base.suffix}"),
            base_text=TextFile(base).read(),
            head_text=TextFile(head).read(),
        )

    def base_definitions(self) -> DefinitionIndex:
        """
        :return: What the base version and the sample's ``other_*.py`` files define, as
            the base commit's definitions.
        """
        files = [
            next(self.directory.glob("base.*")),
            *sorted(self.directory.glob("other_*.py")),
        ]
        return DefinitionIndex(
            SourceDefinitions(tuple(TextFile(file).read() for file in files))
        )


SIGNATURE_DEFINITIONS = DatasetLocation.REVIEW_TRIAGE / "signatures" / "definitions.py"
"""
The file whose definitions the signature suite reads.
"""


# %% pull request descriptions


class DescriptionSample(StrEnum):
    """
    A pull request description, by its file name.
    """

    DECLARING = "description.md"
    WITHOUT_DECLARATION = "description-without-declaration.md"
    REJECTING_RENAME = "description-rejecting-rename.md"

    def read(self) -> str:
        """
        :return: The description.
        """
        return TextFile(DatasetLocation.REVIEW_TRIAGE / self).read()


# %% scopes


class ScopeSample(StrEnum):
    """
    A module whose scopes bind names in a particular way, by its file name.
    """

    GLOBAL_IN_NESTED_FUNCTION = "global-in-nested-function.py"

    def read(self) -> str:
        """
        :return: The module's text.
        """
        return TextFile(DatasetLocation.REVIEW_TRIAGE / "scopes" / self).read()


# %% the pull request


class SampleTrees(StrEnum):
    """
    The parts of a sample pull request kept in one directory, its two trees among them.
    """

    @classproperty
    def directory_name(cls) -> str:
        """
        The name of the directory holding the parts.
        """
        raise NotImplementedError

    @property
    def path(self) -> Path:
        """
        Where the part is.
        """
        return DatasetLocation.REVIEW_TRIAGE / self.directory_name / self

    def files(self) -> dict[Path, str]:
        """
        :return: The content of each file of this tree, by its path in the tree.
        """
        return {
            file.relative_to(self.path): TextFile(file).read()
            for file in self.path.rglob("*")
            if file.is_file()
        }

    def payload(self) -> Any:
        """
        :return: The part's JSON, parsed.
        """
        return json.loads(TextFile(self.path).read())


class PullRequestSample(SampleTrees):
    """
    The parts of the sample pull request: its two trees, its REST payload and its
    report.
    """

    BASE_TREE = "base"
    HEAD_TREE = "head"
    PAYLOAD = "pull-request.json"
    REPORT = "report.md"

    @classproperty
    def directory_name(cls) -> str:
        return "pull-request"


# %% the module move


class ModuleMoveSample(SampleTrees):
    """
    A pull request moving a module into a subpackage and importing it from there.
    """

    BASE_TREE = "base"
    HEAD_TREE = "head"

    @classproperty
    def directory_name(cls) -> str:
        return "module-move"


# %% the definition move


class DefinitionMoveSample(SampleTrees):
    """
    A pull request moving classes out of a module that stays, into one that exists and
    one it adds, and importing them from there.
    """

    BASE_TREE = "base"
    HEAD_TREE = "head"

    @classproperty
    def directory_name(cls) -> str:
        return "definition-move"


class DefinitionMoveFromMovedModuleSample(SampleTrees):
    """
    A pull request moving a module and, out of it, one class into a module it adds.
    """

    BASE_TREE = "base"
    HEAD_TREE = "head"

    @classproperty
    def directory_name(cls) -> str:
        return "definition-move-from-moved-module"


class SubclassSubstitutionSample(SampleTrees):
    """
    A pull request moving a property of a class down into a new subclass, one caller
    switching to the subclass and another keeping the class.
    """

    BASE_TREE = "base"
    HEAD_TREE = "head"

    @classproperty
    def directory_name(cls) -> str:
        return "subclass-substitution"


class BindingRenameSample(SampleTrees):
    """
    A pull request renaming a module's class, and every spelling of its old name with
    it: the class's own uses, an unrelated class of the same name, an external one and
    a string literal.
    """

    BASE_TREE = "base"
    HEAD_TREE = "head"

    @classproperty
    def directory_name(cls) -> str:
        """
        The directory holding the binding-rename sample.
        """
        return "binding-rename"


class AttributeRenameSample(SampleTrees):
    """
    A pull request renaming methods and attributes of classes, with the same names on
    unrelated objects, an override left behind and a standard library override changed
    alike.
    """

    BASE_TREE = "base"
    HEAD_TREE = "head"

    @classproperty
    def directory_name(cls) -> str:
        """
        The directory holding the attribute-rename sample.
        """
        return "attribute-rename"


# %% the base branch merged after a review


class BaseBranchMergeSample(SampleTrees):
    """
    A pull request reviewed once, then merging an update of its base branch and changing
    one file again.
    """

    BASE_TREE = "base"
    """
    The files of the base branch the pull request started from.
    """

    REVIEWED_TREE = "reviewed"
    """
    The files the pull request had changed when it was reviewed.
    """

    BASE_BRANCH_UPDATE = "base-branch-update"
    """
    The files the base branch changed after the review.
    """

    HEAD_TREE = "head"
    """
    The files the pull request changed after merging the update.
    """

    REVIEWS = "reviews.json"
    """
    The pull request's reviews as REST lists them, each ``commit_id`` naming a
    :class:`ReviewedHistory` commit by its field.
    """

    AUTHENTICATED_USER = "authenticated-user.json"
    """
    The account the credential belongs to, as REST describes it.
    """

    @classproperty
    def directory_name(cls) -> str:
        return "base-branch-merge"


SECTIONED_BOARD = DatasetLocation.REVIEW_TRIAGE / "definition-move-sectioned"
"""
Versions of the definition-move sample's board module that hold section headers.
"""

TEMPLATE_REINDENTED = (
    DatasetLocation.REVIEW_TRIAGE / "template-renamed" / "reindented.py.jinja"
)
"""
The renamed template's head version, its renamed line also indented.
"""


# %% the workspace packages plan


class WorkspacePackagesSample(SampleTrees):
    """
    A pull request splitting one package into a directory per distribution, as the
    workspace packages plan does.
    """

    BASE_TREE = "base"
    HEAD_TREE = "head"

    @classproperty
    def directory_name(cls) -> str:
        return "workspace-packages"


# %% rule settings

RULE_SETTINGS = DatasetLocation.REVIEW_TRIAGE / "rules"
"""
The checkouts, each holding a ``pyproject.toml``, the rule settings are read from.
"""
