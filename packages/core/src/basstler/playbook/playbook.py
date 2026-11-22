"""
The components a project runs basstler with, and where a project declares its own.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from basstler.locations import ProjectLocation
from basstler.playbook.component import PlaybookComponent
from basstler.playbook.contribution import PackageContribution
from basstler.playbook.exceptions import ComponentNotInPlaybook, PlaybookNotDeclared

# %% playbooks


@dataclass(frozen=True)
class Playbook:
    """
    The components a project runs basstler with, in order.
    """

    components: tuple[PlaybookComponent, ...]
    """
    Each component in force, in the order its kind's consumer uses them.
    """

    def with_components(self, *components: PlaybookComponent) -> Playbook:
        """
        :param components: Components to add after those the playbook holds.
        :return: A playbook holding both.
        """
        return Playbook((*self.components, *components))

    def without(self, *components: PlaybookComponent) -> Playbook:
        """
        :param components: Components the playbook holds, to leave out.
        :return: A playbook holding every other component.
        :raises ComponentNotInPlaybook: If one of *components* is not in the playbook.
        """
        for component in components:
            if component not in self.components:
                raise ComponentNotInPlaybook(component)
        return Playbook(
            tuple(
                component
                for component in self.components
                if component not in components
            )
        )

    def components_of[ComponentType: PlaybookComponent](
        self, kind: type[ComponentType]
    ) -> tuple[ComponentType, ...]:
        """
        :param kind: A component kind.
        :return: The playbook's components of that kind, in order.
        """
        return tuple(
            component for component in self.components if isinstance(component, kind)
        )


@dataclass(frozen=True)
class DefaultPlaybook(Playbook):
    """
    The playbook of every installed distribution's contribution.
    """

    components: tuple[PlaybookComponent, ...] = field(
        default_factory=PackageContribution.installed_components
    )
    """
    The components of every installed contribution, in the order of
    :meth:`PackageContribution.installed`.
    """


# %% a project's own playbook


class PlaybookFileVariable(StrEnum):
    """
    The module-level names a project's playbook module is read through.
    """

    PLAYBOOK = "playbook"
    """
    The :class:`Playbook` the project runs basstler with.
    """


@dataclass(frozen=True)
class PlaybookFile:
    """
    The module at a project's root that declares the project's own playbook.
    """

    project_root: Path
    """
    The root of the project.
    """

    @property
    def path(self) -> Path:
        """
        Where the module is, whether or not it exists.
        """
        return self.project_root / ProjectLocation.PLAYBOOK

    def read(self) -> Playbook:
        """
        :return: The playbook the module declares, or a :class:`DefaultPlaybook` when
            the project has no such module.
        :raises PlaybookNotDeclared: If the module declares no :class:`Playbook` under
            :attr:`PlaybookFileVariable.PLAYBOOK`.
        """
        if not self.path.is_file():
            return DefaultPlaybook()
        specification = importlib.util.spec_from_file_location(
            ProjectLocation.PLAYBOOK.stem, self.path
        )
        module = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(module)
        playbook = vars(module).get(PlaybookFileVariable.PLAYBOOK)
        if not isinstance(playbook, Playbook):
            raise PlaybookNotDeclared(self.path, PlaybookFileVariable.PLAYBOOK)
        return playbook
