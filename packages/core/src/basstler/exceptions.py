"""
Krrood's ``DataclassException`` and the errors built on it.

``DataclassException`` is copied from krrood :cite:`krrood` until krrood's light core is
released.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from basstler.class_property import classproperty
from basstler.exit_codes import CommandFailure, StackExitCode
from basstler.locations import BasstlerVariable, ClaudeCodeVariable, PluginLocation

if TYPE_CHECKING:
    from basstler.module import Module


class DataclassException(Exception, ABC):
    """
    A base exception class for dataclass-based exceptions.

    Subclasses implement error_message() and suggest_correction(); both are evaluated at
    construction time and composed into the actual exception message (the args passed to
    Exception). A non-empty suggest_correction() is rendered as a trailing "Suggestion:
    ..." line. Subclasses that override __post_init__ must call super().__post_init__()
    at the end.
    """

    def __post_init__(self) -> None:
        # BaseException.__new__ bypasses the usual ABC instantiation check, so enforce it here.
        if getattr(type(self), "__abstractmethods__", None):
            raise TypeError(
                f"Can't instantiate abstract class {type(self).__name__} without an implementation of "
                f"{', '.join(sorted(type(self).__abstractmethods__))}."
            )
        message = self.error_message()
        correction = self.suggest_correction()
        if correction:
            message = f"{message}\nSuggestion: {correction}"
        super().__init__(message)

    def __str__(self) -> str:
        # Stdlib mixins like KeyError override __str__ to repr their args; always render the
        # plain message that __post_init__ baked into the args.
        return Exception.__str__(self)

    @abstractmethod
    def error_message(self) -> str:
        """
        :return: A human-readable description of what went wrong.
        """

    @abstractmethod
    def suggest_correction(self) -> str:
        """
        :return: Advice on how to fix the error, or an empty string if there is no specific advice.
        """


@dataclass
class UnresolvableReferenceError(CommandFailure, DataclassException, LookupError):
    """
    Raised when a git reference a decision depends on names no commit in the checkout.
    """

    @classproperty
    def exit_code(cls) -> StackExitCode:
        """:return: The status this kind of error ends a command with."""
        return StackExitCode.GIT_COMMAND_FAILED

    reference: str
    """
    The reference git could not resolve.
    """

    def error_message(self) -> str:
        return f"git cannot resolve '{self.reference}' to a commit in this checkout"

    def suggest_correction(self) -> str:
        return (
            "fetch the branch it names from its remote, and check that the branch "
            "still exists there"
        )


@dataclass
class MissingStatusLineError(DataclassException, ValueError):
    """
    Raised when an item slated for a status correction has no ``status:`` line in its
    plan.yaml block.
    """

    item_identifier: str
    """
    The id of the item whose block has no ``status:`` line.
    """

    def error_message(self) -> str:
        return f"item {self.item_identifier!r} has no status: line to correct"

    def suggest_correction(self) -> str:
        return "give the item a status: line in plan.yaml"


# %% calls to git and GitHub


@dataclass
class ExternalCallFailed(DataclassException, RuntimeError):
    """
    Base for a call to git or GitHub that the caller depended on and did not get.

    Both carry what was called, the status it came back with and what it said, and
    differ only in how they name the call.
    """

    status: int
    """The status the call came back with."""

    detail: str
    """
    What the far side said about it.
    """

    @property
    def call(self) -> str:
        """:return: The call that failed, named the way its own caller named it."""
        raise NotImplementedError

    def error_message(self) -> str:
        return f"{self.call} failed with {self.status}: {self.detail}"

    def suggest_correction(self) -> str:
        return ""


@dataclass
class MalformedEmailAddressError(DataclassException, ValueError):
    """
    Raised when text is not an email address in ``local-part@domain`` form.
    """

    text: str
    """
    The value that could not be parsed.
    """

    def error_message(self) -> str:
        return f"expected an email address as 'local-part@domain', got {self.text!r}"

    def suggest_correction(self) -> str:
        return "give the address your commits should carry, e.g. you@example.com"


@dataclass
class ModuleOutsideRootError(DataclassException, ValueError):
    """
    Raised when a module is named relative to a root that does not hold it.
    """

    module: Module
    """
    The module that was named relative to :attr:`root`.
    """

    root: Module
    """
    The package or module that does not hold :attr:`module`.
    """

    def error_message(self) -> str:
        return f"{self.module.absolute} is not within {self.root.absolute}"

    def suggest_correction(self) -> str:
        return f"name a module that starts with {self.root.absolute}"


@dataclass
class BashNotFoundError(DataclassException, FileNotFoundError):
    """
    Raised when no bash a script can run in is found, the Windows launcher for WSL
    aside.
    """

    passed_over: list[Path]
    """
    The bash programs found in the Windows directory, which start WSL rather than the
    bash the scripts are written for.
    """

    def error_message(self) -> str:
        if not self.passed_over:
            return "found no bash to run the plugin's scripts in"
        launchers = ", ".join(str(path) for path in self.passed_over)
        return (
            f"found no bash to run the plugin's scripts in: {launchers} starts WSL, not "
            f"Git Bash"
        )

    def suggest_correction(self) -> str:
        return (
            f"install Git for Windows, or set {ClaudeCodeVariable.GIT_BASH_PATH} to its "
            f"bash.exe"
        )


@dataclass
class PluginRootUnsetError(DataclassException, LookupError):
    """
    Raised when no plugin root is exported, so no plugin script can be found.
    """

    def error_message(self) -> str:
        return (
            f"{BasstlerVariable.PLUGIN_ROOT} is not set, so the plugin cannot be found"
        )

    def suggest_correction(self) -> str:
        return (
            f"source {PluginLocation.PERSONAL_NOTES_CONFIGURATION_SCRIPT} from the "
            f"plugin's root first, or export {BasstlerVariable.PLUGIN_ROOT} as that root"
        )


@dataclass
class PluginRootNotADirectoryError(DataclassException, NotADirectoryError):
    """
    Raised when the exported plugin root is not a directory.
    """

    root: Path
    """
    The plugin root exported.
    """

    def error_message(self) -> str:
        return f"{BasstlerVariable.PLUGIN_ROOT} names {self.root}, which is not a directory"

    def suggest_correction(self) -> str:
        return (
            f"export {BasstlerVariable.PLUGIN_ROOT} as the directory holding the "
            f"plugin's {PluginLocation.HOOKS} directory"
        )


class PackageMapInconsistency(StrEnum):
    """
    The ways the declared distributions break their layering.
    """

    DEPENDENCY_ON_A_HIGHER_LAYER = "depends on a distribution in a higher layer"
    """
    The first distribution lists the second, which sits in a higher layer.
    """

    DEPENDENCY_CYCLE = "depend on each other in a cycle"
    """
    The distributions, in order, each list the next and the last lists the first.
    """

    UNDECLARED_DISTRIBUTION = "has no declaration"
    """
    The distribution is listed as a dependency, but nothing declares it.
    """

    MODULE_CLAIMED_TWICE = "both claim the same module"
    """
    Two distributions name the same module or subpackage.
    """


@dataclass
class InconsistentPackageMap(DataclassException, ValueError):
    """
    The declared distributions are not layered and acyclic.
    """

    inconsistency: PackageMapInconsistency
    """
    How the declarations break the layering.
    """

    distributions: tuple[str, ...]
    """
    The package names of the distributions involved.
    """

    def error_message(self) -> str:
        return f"{', '.join(self.distributions)} {self.inconsistency}"

    def suggest_correction(self) -> str:
        return "correct the dependencies in the distributions' pyproject.toml files"


@dataclass
class UndeclaredDistribution(DataclassException, KeyError):
    """
    A declaration was looked up for a distribution the package map does not declare.
    """

    distribution: str
    """
    The package name of the distribution looked up.
    """

    def error_message(self) -> str:
        return f"{self.distribution} {PackageMapInconsistency.UNDECLARED_DISTRIBUTION}"

    def suggest_correction(self) -> str:
        return "add its directory under packages or look up a declared one"


@dataclass
class DuplicateKeyError(DataclassException, TypeError):
    """
    Raised when two fields of a model read the same key of the object it mirrors.
    """

    model: str
    """
    The model's name.
    """

    key: str
    """
    The key both fields read.
    """

    fields: tuple[str, str]
    """
    The two fields reading it.
    """

    def error_message(self) -> str:
        first, second = self.fields
        return f"{self.model}.{first} and {self.model}.{second} both read {self.key!r}"

    def suggest_correction(self) -> str:
        return "Give one of the fields the key it should read instead as its alias."
