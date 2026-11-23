"""
The names of the ``basstler plan-handover`` commands and of the options their messages
and the plan site name.
"""

from __future__ import annotations

from enum import StrEnum

from basstler.basstler_command import BasstlerCommand
from basstler.class_property import classproperty

# %% the commands


class PlanHandoverCommand(BasstlerCommand):
    """
    The ``basstler plan-handover`` command group and its commands, by name.
    """

    @classproperty
    def group(cls) -> str:
        return "plan-handover"

    EXPORT = "export"
    """
    Write plans into a directory.
    """

    OFFER = "offer"
    """
    Offer plans to another person as a pull request on their repository.
    """

    DELETE_BRANCHES = "delete-branches"
    """
    Delete the branches of handed-over items the receiver continues.
    """

    REMOVE = "remove"
    """
    Remove handed-over plans from this repository's notes branch.
    """

    IMPORT = "import"
    """
    Take a handover on.
    """


# %% the options


class PlanHandoverOption(StrEnum):
    """
    An option of a ``basstler plan-handover`` command.
    """

    PULL_REQUEST = "--pull-request"
    """
    The number of the one handover pull request an import takes over.
    """

    ALL = "--all"
    """
    Take over every handover pull request open on the repository.
    """

    RECEIVER_REPOSITORY = "--receiver-repository"
    """
    The repository the receiver continues the plans on, as ``owner/name``.
    """

    RECEIVER_LOGIN = "--receiver-login"
    """
    The receiver's GitHub login.
    """

    WITHOUT_DEPENDENCIES = "--without-dependencies"
    """
    Hand plans over without the plans they depend on.
    """
