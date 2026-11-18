"""
Reading one REST resource of a repository into the model of its type, and writing a
setting with the step that takes it by hand when GitHub refuses.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, get_args, get_origin

from basstler.class_property import classproperty
from basstler.github.client import GitHubAttemptReader, GitHubResponse, RepositoryWrite
from basstler.github.repository import RepositoryMember
from basstler.github.user_steps import UserStep
from basstler.json_model import ValidatedJSONModel

# %% the type a read or a write is bound to


class TypeBinding:
    """
    A class whose subclasses each bind a generic base's parameter to the type they
    handle.
    """

    @classmethod
    def bound_type_argument(cls, generic_base: type) -> type[Any]:
        """
        :param generic_base: The generic class whose parameter is bound.
        :return: The type this class binds it to, directly or through a base.
        :raises TypeError: If this class leaves the parameter unbound.
        """
        for klass in cls.__mro__:
            for base in klass.__dict__.get("__orig_bases__", ()):
                origin = get_origin(base)
                if isinstance(origin, type) and issubclass(origin, generic_base):
                    (argument,) = get_args(base)
                    if isinstance(argument, type):
                        return argument
        raise TypeError(f"{cls.__name__} binds no type to {generic_base.__name__}")


# %% reading a resource


@dataclass(frozen=True)
class ResourceReading[ResourceType: ValidatedJSONModel]:
    """
    GitHub's answer to one read, with the resource parsed when it was served.
    """

    response: GitHubResponse
    """
    GitHub's answer.
    """

    resource: ResourceType | None
    """
    The resource read, ``None`` when GitHub refused or found none.
    """


@dataclass(frozen=True)
class RepositoryRead[ResourceType: ValidatedJSONModel](
    RepositoryMember, TypeBinding, ABC
):
    """
    A read of one REST resource of a repository, bound to the model the resource parses
    into.
    """

    @property
    @abstractmethod
    def path(self) -> str:
        """
        The resource's REST path.
        """

    @classproperty
    def resource_type(cls) -> type[ResourceType]:
        """
        The model this read is bound to.
        """
        return cls.bound_type_argument(RepositoryRead)

    def attempt(self, client: GitHubAttemptReader) -> ResourceReading[ResourceType]:
        """
        :param client: Reads the repository.
        :return: GitHub's answer, with the resource parsed when it was served.
        """
        response = client.attempt_get(self.path)
        if response.failure is not None:
            return ResourceReading(response, None)
        return ResourceReading(response, self.resource_type.from_json(response.body))


# %% writing a setting


class SettingWrite[ResourceType: ValidatedJSONModel](TypeBinding, RepositoryWrite, ABC):
    """
    A change to one setting of a repository, bound to the model of the setting it
    changes.
    """

    @classproperty
    def setting_type(cls) -> type[ResourceType]:
        """
        The model of the setting this write changes.
        """
        return cls.bound_type_argument(SettingWrite)

    @property
    @abstractmethod
    def manual_step(self) -> UserStep:
        """
        The same change, as the step the user takes when GitHub refuses the write.
        """
