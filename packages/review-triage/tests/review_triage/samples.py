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
    COMMENT_REWORDED = "comment-reworded"
    CONFLICT_MARKERS = "conflict-markers"
    DOCSTRING_ADDED_OVER_CODE = "docstring-added-over-code"
    DOCSTRING_REFLOWED = "docstring-reflowed"
    DOCSTRING_REWORDED = "docstring-reworded"
    DOCUMENTATION_IMPORT_MOVED = "documentation-import-moved"
    DOCUMENTED_RECEIVER_BINDS_DIFFERENTLY = "documented-receiver-binds-differently"
    DOCUMENTATION_REFLOWED = "documentation-reflowed"
    DOCUMENTATION_RENAMED = "documentation-renamed"
    IDENTIFIER_RENAMED = "identifier-renamed"
    IDENTITY_DECORATOR_ADDED = "identity-decorator-added"
    IDENTITY_DECORATOR_IMPORTED = "identity-decorator-imported"
    IMPORT_ADDED_FROM_OTHER_MODULE = "import-added-from-other-module"
    IMPORT_ADDED_UNDER_STAR_IMPORT = "import-added-under-star-import"
    IMPORT_ADDED_UNUSED = "import-added-unused"
    IMPORT_REMOVED_UNUSED = "import-removed-unused"
    IMPORT_SOURCE_CHANGED = "import-source-changed"
    IMPORTED_DECORATOR_NOT_IDENTITY = "imported-decorator-not-identity"
    IMPORTS_REORDERED = "imports-reordered"
    KEYWORD_ARGUMENTS_ADDED = "keyword-arguments-added"
    KEYWORD_ARGUMENTS_ADDED_THROUGH_IMPORT_ALIAS = (
        "keyword-arguments-added-through-import-alias"
    )
    KEYWORD_ARGUMENTS_REORDERED = "keyword-arguments-reordered"
    KEYWORD_ARGUMENTS_SWAPPED = "keyword-arguments-swapped"
    KEYWORD_ARGUMENTS_UNKNOWN_CALLEE = "keyword-arguments-unknown-callee"
    KEYWORD_ONLY_PARAMETERS = "keyword-only-parameters"
    MODULE_DOCUMENTATION_AND_CODE_CHANGED = "module-documentation-and-code-changed"
    MODULE_DOCUMENTATION_REWORDED = "module-documentation-reworded"
    PROPERTY_READ_AS_ABSTRACT_METHOD_OF_A_SHARED_CLASS_NAME = (
        "property-read-as-abstract-method-of-a-shared-class-name"
    )
    PROPERTY_READ_AS_ABSTRACT_INTERFACE_METHOD = (
        "property-read-as-abstract-interface-method"
    )
    PROPERTY_READ_AS_METHOD_CALL = "property-read-as-method-call"
    PROPERTY_READ_AS_METHOD_CALL_UNPROVEN = "property-read-as-method-call-unproven"
    PROPERTY_READ_AS_UNENFORCED_ABSTRACT_METHOD = (
        "property-read-as-unenforced-abstract-method"
    )
    PROPERTY_READ_AS_UNIMPLEMENTED_ABSTRACT_METHOD = (
        "property-read-as-unimplemented-abstract-method"
    )
    RECEIVER_BINDS_DIFFERENTLY = "receiver-binds-differently"
    RECEIVER_OVERRIDES_INCOMPATIBLE = "receiver-overrides-incompatible"
    RECEIVER_REBOUND_OUT_OF_ORDER = "receiver-rebound-out-of-order"
    RECEIVER_TYPE_AMBIGUOUS = "receiver-type-ambiguous"
    RECEIVER_TYPE_FOLLOWED = "receiver-type-followed"
    RECEIVER_TYPE_INFERRED = "receiver-type-inferred"
    RECEIVER_PARAMETER_REASSIGNED = "receiver-parameter-reassigned"
    RECEIVER_PARAMETER_REBOUND_IN_LOOP = "receiver-parameter-rebound-in-loop"
    RECEIVER_TYPE_REASSIGNED = "receiver-type-reassigned"
    RECEIVER_TYPE_UNKNOWN = "receiver-type-unknown"
    RELATIVE_IMPORT_MOVED = "relative-import-moved"
    STATEMENT_APPENDED = "statement-appended"
    STRING_LITERAL_RENAMED = "string-literal-renamed"
    TEMPLATE_RENAMED = "template-renamed"
    UTF_8_AND_TREE_REMOVAL_FIXES = "utf-8-and-tree-removal-fixes"
    BASH_AND_UTF_8_FIXES = "bash-and-utf-8-fixes"
    POSIX_PATH_AND_UTF_8_FIXES = "posix-path-and-utf-8-fixes"
    BASH_POSIX_PATH_AND_UTF_8_FIXES = "bash-posix-path-and-utf-8-fixes"
    FILE_URI_AND_UTF_8_FIXES = "file-uri-and-utf-8-fixes"
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
        :return: The change from the base to the head version, at a path with the head
            version's suffix.
        """
        base = next(self.directory.glob("base.*"))
        head = next(self.directory.glob("head.*"))
        return FileVersions(
            PurePosixPath(f"sample{head.suffix}"),
            base_text=TextFile(base).read(),
            head_text=TextFile(head).read(),
        )

    def head_line(self, code: str) -> int:
        """
        :param code: A line of the head version, without its indentation.
        :return: The number of the first line of the head version reading so.
        """
        lines = [line.strip() for line in self.change().head_text.splitlines()]
        return lines.index(code) + 1

    def base_definitions(self) -> DefinitionIndex:
        """
        :return: What the base version and the sample's ``other_*.py`` files define, as
            the base commit's definitions.
        """
        return self.commit_definitions("base.*", "other_*.py")

    def head_definitions(self) -> DefinitionIndex:
        """
        :return: What the head version and the sample's ``head_other_*.py`` files
            define, as the head commit's definitions.
        """
        return self.commit_definitions("head.*", "head_other_*.py")

    def commit_definitions(self, version: str, others: str) -> DefinitionIndex:
        """
        :param version: The pattern of the file of one version of the sample.
        :param others: The pattern of the further files of that version's commit.
        :return: What those files define.
        """
        files = [
            next(self.directory.glob(version)),
            *sorted(self.directory.glob(others)),
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
    INVALID_ESCAPE_SEQUENCE = "invalid-escape-sequence.py"

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


# %% an import respelled to another module that still exists


class ModuleNameKeptSample(SampleTrees):
    """
    A pull request respelling an import to another module binding another object of the
    same name, while the module it imported from stays.
    """

    BASE_TREE = "base"
    HEAD_TREE = "head"

    @classproperty
    def directory_name(cls) -> str:
        return "module-name-kept"


# %% an import respelled to the module a re-export reads from


class ReexportedImportSample(SampleTrees):
    """
    A pull request moving two classes out of a module that re-exports one of them and
    binds the other's name to a different class, with a caller importing each from its
    new module.
    """

    BASE_TREE = "base"
    HEAD_TREE = "head"

    @classproperty
    def directory_name(cls) -> str:
        return "reexported-import"


# %% the package root move


class PackageRootMoveSample(SampleTrees):
    """
    A pull request moving a package, ``__init__.py`` files and all, under a directory
    that is not a package, leaving its modules' dotted paths as they were.
    """

    BASE_TREE = "base"
    HEAD_TREE = "head"

    @classproperty
    def directory_name(cls) -> str:
        return "package-root-move"


# %% empty package initializers moved apart


class AmbiguousPackageInitializersSample(SampleTrees):
    """
    A pull request splitting one ``tests`` package into two, whose many identical, empty
    ``__init__.py`` files git pairs with each other in no meaningful order.
    """

    BASE_TREE = "base"
    HEAD_TREE = "head"

    @classproperty
    def directory_name(cls) -> str:
        return "ambiguous-package-initializers"


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


class DefinitionMoveAgainstRenameSample(SampleTrees):
    """
    A pull request renaming a class in its module and adding a different class of the
    old name to another module.
    """

    BASE_TREE = "base"
    HEAD_TREE = "head"

    @classproperty
    def directory_name(cls) -> str:
        return "definition-move-against-rename"


class DefinitionMoveAndRenameSample(SampleTrees):
    """
    A pull request moving a class to another module under a new name, and importing it
    from there by that name.
    """

    BASE_TREE = "base"
    HEAD_TREE = "head"

    @classproperty
    def directory_name(cls) -> str:
        return "definition-move-and-rename"


class DefinitionMovePackageRootSample(SampleTrees):
    """
    A pull request moving a class into a new module of a package moved out of ``src/``,
    a directory that is not a package, and importing it from there relatively.
    """

    BASE_TREE = "base"
    HEAD_TREE = "head"

    @classproperty
    def directory_name(cls) -> str:
        return "definition-move-package-root"


class DefinitionMoveNamespacePackageSample(SampleTrees):
    """
    A pull request moving a class between two projects of the ``src`` layout that share
    a namespace package, which has no initializer, and importing it from its new module.
    """

    BASE_TREE = "base"
    HEAD_TREE = "head"

    @classproperty
    def directory_name(cls) -> str:
        return "definition-move-namespace-package"


class AttributeMoveSample(SampleTrees):
    """
    A pull request moving an enumeration member into a class of a module it adds, and
    reading the member from there; its variants each change the class it moves into.
    """

    BASE_TREE = "base"
    HEAD_TREE = "head"
    OTHER_VALUE = "variants/other_value.py"
    OTHER_BASE = "variants/other_base.py"
    ADDED_METHOD = "variants/added_method.py"
    RE_EXPORTING_USER = "variants/re_exporting_user.py"
    LOCATIONS_WITH_METHOD_BASE = "variants/locations_with_method_base.py"
    LOCATIONS_WITH_METHOD_HEAD = "variants/locations_with_method_head.py"
    UNMOVED_FILE_NAME_READER = "variants/unmoved_file_name_reader.py"
    MOVED_FILE_NAME_READER_BASE = "variants/moved_file_name_reader_base.py"
    MOVED_FILE_NAME_READER_HEAD = "variants/moved_file_name_reader_head.py"
    OTHER_LOSER_BASE = "variants/other_loser_base.py"
    OTHER_LOSER_HEAD = "variants/other_loser_head.py"

    @classproperty
    def directory_name(cls) -> str:
        return "attribute-move"


class ViewedStateSample(SampleTrees):
    """
    A pull request of two commits whose files the viewer viewed, never viewed, or viewed
    at its first commit before the second changed them.
    """

    BASE_TREE = "base"
    CHECKPOINT_TREE = "checkpoint"
    HEAD_TREE = "head"

    @classproperty
    def directory_name(cls) -> str:
        return "viewed-state"


class DefinitionMoveSameModulePathSample(SampleTrees):
    """
    A pull request moving a module's function into a module of the same dotted path that
    it adds in a package kept under ``packages/``.
    """

    BASE_TREE = "base"
    HEAD_TREE = "head"

    @classproperty
    def directory_name(cls) -> str:
        return "definition-move-same-module-path"


class SubclassSubstitutionSourceLayoutSample(SampleTrees):
    """
    A pull request switching a caller to a new subclass in a package kept under
    ``src/``, importing both classes relatively.
    """

    BASE_TREE = "base"
    HEAD_TREE = "head"

    @classproperty
    def directory_name(cls) -> str:
        return "subclass-substitution-source-layout"


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


class PropertyBindingRenameSample(SampleTrees):
    """
    A pull request renaming module classes and turning their properties into methods:
    one reproducing its property under the renames, one whose body names an unrelated
    class of the renamed class's old name.
    """

    BASE_TREE = "base"
    HEAD_TREE = "head"

    @classproperty
    def directory_name(cls) -> str:
        return "property-read-renamed-by-binding"


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


class AttributeInheritedInHeadSample(SampleTrees):
    """
    A pull request dropping a method from a class that now inherits it, while the class
    adds a method of another name.
    """

    BASE_TREE = "base"
    HEAD_TREE = "head"

    @classproperty
    def directory_name(cls) -> str:
        """
        The directory holding the attribute-inherited-in-head sample.
        """
        return "attribute-inherited-in-head"
