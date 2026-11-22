"""
What one distribution adds to the default playbook, and how the installed ones are found.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum
from importlib.metadata import entry_points

from basstler.class_property import classproperty
from basstler.playbook.component import PlaybookComponent

# %% registration


class ContributionEntryPointGroup(StrEnum):
    """
    The entry point group an installed distribution registers its contribution under.
    """

    CONTRIBUTIONS = "basstler.contributions"
    """
    Each entry names a :class:`PackageContribution` subclass.
    """


# %% contributions


class PackageContribution(ABC):
    """
    The components one distribution adds to the default playbook.
    """

    @classproperty
    @abstractmethod
    def components(cls) -> tuple[PlaybookComponent, ...]:
        """
        The distribution's components, in the order a playbook lists them.
        """

    @classmethod
    def installed(cls) -> tuple[type[PackageContribution], ...]:
        """
        :return: Every contribution an installed distribution registers under
            :attr:`ContributionEntryPointGroup.CONTRIBUTIONS`, in the order of their
            entry point names.
        """
        registered = entry_points(group=ContributionEntryPointGroup.CONTRIBUTIONS)
        return tuple(
            entry.load() for entry in sorted(registered, key=lambda entry: entry.name)
        )

    @classmethod
    def installed_components(cls) -> tuple[PlaybookComponent, ...]:
        """
        :return: The components of every contribution in :meth:`installed`, in that
            order.
        """
        return tuple(
            component
            for contribution in cls.installed()
            for component in contribution.components
        )
