"""
The setup steps a repository checkout leaves to its user, which each distribution
contributes for its own subject.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from basstler.class_property import classproperty
from basstler.playbook.component import PlaybookComponent
from basstler.playbook.playbook import Playbook

# %% one step


@dataclass(frozen=True)
class SetupStep(ABC):
    """
    One setup step basstler leaves to its user, because it changes a setting held by
    GitHub or by Claude, which basstler holds no credential or approval to change.
    """

    @property
    @abstractmethod
    def title(self) -> str:
        """
        What the step changes, in a few words.
        """

    @property
    @abstractmethod
    def reason(self) -> str:
        """
        What stops working until it is done.
        """

    @abstractmethod
    def instructions(self) -> list[str]:
        """
        What to do, one line per action.

        :return: The lines, printed under the title.
        """

    def render(self, number: int) -> str:
        """
        Render this step as the numbered block the reader sees.

        :param number: The step's position in the printed list.
        :return: The block, without a trailing newline.
        """
        lines = [f"{number}. {self.title}", f"   {self.reason}", ""]
        lines.extend(f"   {instruction}" for instruction in self.instructions())
        return "\n".join(lines)


# %% the steps a distribution contributes


@dataclass(frozen=True)
class RepositoryCheckout:
    """
    A local checkout of the repository basstler runs in, together with the environment
    its settings resolve from.
    """

    working_tree: Path
    """
    The directory the repository is checked out in.
    """

    environment: Mapping[str, str]
    """
    The environment its settings resolve from.
    """


@dataclass(frozen=True)
class SetupSteps(PlaybookComponent, ABC):
    """
    The setup steps one distribution leaves to the user of a repository checkout.
    """

    @abstractmethod
    def steps_for_repository_checkout(
        self, repository_checkout: RepositoryCheckout
    ) -> tuple[SetupStep, ...]:
        """
        :param repository_checkout: The repository checkout the steps are about.
        :return: The steps that apply to it, in the order they should be done.
        """


# %% the checklist they add up to


@dataclass(frozen=True)
class SetupChecklist:
    """
    The steps one repository checkout leaves to its user, in the order they should be
    done.
    """

    steps: tuple[SetupStep, ...]
    """
    The steps that apply to this repository checkout.
    """

    @classproperty
    def heading(cls) -> str:
        """
        The line introducing the printed list.
        """
        return "These steps are yours - no script can do them:"

    @classmethod
    def from_repository_checkout(
        cls, playbook: Playbook, repository_checkout: RepositoryCheckout
    ) -> SetupChecklist:
        """
        :param playbook: The playbook whose :class:`SetupSteps` apply.
        :param repository_checkout: The repository checkout the steps are about.
        :return: The steps of every :class:`SetupSteps` in the playbook, in its order.
        """
        return cls(
            tuple(
                step
                for setup_steps in playbook.components_of(SetupSteps)
                for step in setup_steps.steps_for_repository_checkout(
                    repository_checkout
                )
            )
        )

    def render(self) -> str:
        """
        Render the whole checklist as it is printed.

        :return: The full output.
        """
        blocks = [
            step.render(number) for number, step in enumerate(self.steps, start=1)
        ]
        return "\n\n".join([self.heading, *blocks])
