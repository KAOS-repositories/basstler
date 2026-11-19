"""
The forms GitHub's payloads write a branch in, each read into the :class:`Branch` it
names and written back from it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import GetCoreSchemaHandler, ValidationInfo
from pydantic_core import core_schema

from basstler.git.branch import Branch
from basstler.github.exceptions import BranchOwnerUnknown
from basstler.github.repository import HasRepository, Repository
from basstler.json_model import ObjectReader

# %% the form


class BranchWireForm[BranchType: Branch[Repository]](ABC):
    """
    A field annotation reading a branch from the form a payload writes it in, and
    writing it back in that form.
    """

    @abstractmethod
    def read(self, value: Any, read: HasRepository | None) -> BranchType:
        """
        :param value: The branch as the payload writes it.
        :param read: The read that was served the payload, ``None`` when there is none.
        :return: The branch.
        """

    @abstractmethod
    def write(self, branch: BranchType) -> Any:
        """
        :param branch: A branch.
        :return: The branch as the payload writes it.
        """

    def __get_pydantic_core_schema__(
        self, source: type[Any], handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        """
        :param source: The field's type.
        :param handler: Builds pydantic's own schema for a type.
        :return: How pydantic reads and writes the field: :meth:`read` and
            :meth:`write`, a missing branch left as ``None``.
        """

        def read_field(value: Any, information: ValidationInfo) -> BranchType | None:
            if value is None or isinstance(value, Branch):
                return value
            return self.read(value, information.context)

        return core_schema.with_info_plain_validator_function(
            read_field,
            serialization=core_schema.plain_serializer_function_ser_schema(
                self.write, when_used="unless-none"
            ),
        )


# %% a branch of the repository read


class ReadRepositoryBranchForm(BranchWireForm[Branch[Repository]], ABC):
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
            raise BranchOwnerUnknown(name)
        return Branch(read.repository, name)


class BranchName(ReadRepositoryBranchForm):
    """
    A branch written as its bare name, ``main``.
    """

    def name_in(self, text: str) -> str:
        return text

    def write(self, branch: Branch[Repository]) -> str:
        return branch.name


class BranchFullReference(ReadRepositoryBranchForm):
    """
    A branch written as the full reference it is kept under, ``refs/heads/main``.
    """

    def name_in(self, text: str) -> str:
        return text.removeprefix(f"{Branch.namespace}/")

    def write(self, branch: Branch[Repository]) -> str:
        return branch.reference


# %% a branch of a repository the payload names


class RepositoryDefaultBranch(BranchWireForm[Branch[Repository]], ObjectReader):
    """
    A repository's default branch, written as the repository resource that names it.
    """

    @property
    def read_keys(self) -> frozenset[str]:
        return frozenset({"full_name", "default_branch"})

    def read(self, value: Any, read: HasRepository | None) -> Branch[Repository]:
        return Branch(Repository.parse(value["full_name"]), value["default_branch"])

    def write(self, branch: Branch[Repository]) -> dict[str, str]:
        return {
            "full_name": branch.repository.full_name,
            "default_branch": branch.name,
        }
