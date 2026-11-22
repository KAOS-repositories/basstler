"""
The forms GitHub's payloads write a thing a repository owns in - a branch, a pull
request - each read into the model of what it names and written back from it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from types import UnionType
from typing import Any, Union, get_args, get_origin

from pydantic import GetCoreSchemaHandler, ValidationInfo
from pydantic_core import core_schema

from basstler.git.branch import Branch
from basstler.github.exceptions import RepositoryUnknown
from basstler.github.repository import HasRepository, PullRequestReference, Repository
from basstler.json_model import ObjectReader

UNION_ORIGINS = (Union, UnionType)
"""
What a union type, ``X | None`` included, reports as its origin.
"""

# %% the form


class WireForm[ValueType](ABC):
    """
    A field annotation reading a thing a repository owns from the form a payload writes
    it in, and writing it back in that form.
    """

    @abstractmethod
    def read(self, value: Any, read: HasRepository | None) -> ValueType:
        """
        :param value: The thing as the payload writes it.
        :param read: The read that was served the payload, ``None`` when there is none.
        :return: The thing.
        """

    @abstractmethod
    def write(self, owned: ValueType) -> Any:
        """
        :param owned: The thing.
        :return: It, as the payload writes it.
        """

    def __get_pydantic_core_schema__(
        self, source: type[Any], handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        """
        :param source: The field's type.
        :param handler: Builds pydantic's own schema for a type.
        :return: How pydantic reads and writes the field: :meth:`read` and
            :meth:`write`, a missing value left as ``None`` and a built one as it is.
        """
        alternatives = get_args(source) if get_origin(source) in UNION_ORIGINS else ()
        value_types = tuple(
            get_origin(alternative) or alternative
            for alternative in alternatives or (source,)
        )

        def read_field(value: Any, information: ValidationInfo) -> ValueType | None:
            if value is None or isinstance(value, value_types):
                return value
            return self.read(value, information.context)

        return core_schema.with_info_plain_validator_function(
            read_field,
            serialization=core_schema.plain_serializer_function_ser_schema(
                self.write, when_used="unless-none"
            ),
        )


# %% a branch of the repository read


class ReadRepositoryBranchForm(WireForm[Branch[Repository]], ABC):
    """
    A form naming a branch of the repository the payload was read from, by text alone.
    """

    @abstractmethod
    def name_in(self, text: str) -> str:
        """
        :param text: The branch as the payload writes it.
        :return: The branch's name.
        """

    def read(self, value: Any, read: HasRepository | None) -> Branch[Repository]:
        name = self.name_in(value)
        if read is None:
            raise RepositoryUnknown(name)
        return Branch(read.repository, name)


class BranchName(ReadRepositoryBranchForm):
    """
    A branch written as its bare name, ``main``.
    """

    def name_in(self, text: str) -> str:
        return text

    def write(self, owned: Branch[Repository]) -> str:
        return owned.name


class BranchFullReference(ReadRepositoryBranchForm):
    """
    A branch written as the full reference it is kept under, ``refs/heads/main``.
    """

    def name_in(self, text: str) -> str:
        return text.removeprefix(f"{Branch.namespace}/")

    def write(self, owned: Branch[Repository]) -> str:
        return owned.reference


# %% a branch of a repository the payload names


class RepositoryDefaultBranch(WireForm[Branch[Repository]], ObjectReader):
    """
    A repository's default branch, written as the repository resource that names it.
    """

    @property
    def read_keys(self) -> frozenset[str]:
        return frozenset({"full_name", "default_branch"})

    def read(self, value: Any, read: HasRepository | None) -> Branch[Repository]:
        return Branch(Repository.parse(value["full_name"]), value["default_branch"])

    def write(self, owned: Branch[Repository]) -> dict[str, str]:
        return {
            "full_name": owned.repository.full_name,
            "default_branch": owned.name,
        }


# %% a pull request of the repository read


class PullRequestNumber(WireForm[PullRequestReference]):
    """
    A pull request of the repository the payload was read from, written as its number.
    """

    def read(self, value: Any, read: HasRepository | None) -> PullRequestReference:
        if read is None:
            raise RepositoryUnknown(f"#{value}")
        return PullRequestReference(read.repository, value)

    def write(self, owned: PullRequestReference) -> int:
        return owned.number
