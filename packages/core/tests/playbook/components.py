"""
Components and contributions the playbook tests build playbooks from.
"""

from __future__ import annotations

from dataclasses import dataclass

from basstler.class_property import classproperty
from basstler.playbook.component import PlaybookComponent
from basstler.playbook.contribution import PackageContribution
from basstler.playbook.setup_steps import RepositoryCheckout, SetupStep, SetupSteps
from basstler.playbook.skill import Skill
from basstler.session_tool import BuiltInTool, SessionTool

# %% components of two kinds


@dataclass(frozen=True)
class LabelledComponent(PlaybookComponent):
    """
    A component of one kind, told apart by its label.
    """

    label: str
    """
    What tells it apart from another of its kind.
    """


@dataclass(frozen=True)
class OtherKindComponent(PlaybookComponent):
    """
    A component of a second kind.
    """

    label: str
    """
    What tells it apart from another of its kind.
    """


# %% contributions


class EarlierContribution(PackageContribution):
    """
    A contribution registered under the entry point name sorting first.
    """

    @classproperty
    def playbook_components(cls) -> tuple[PlaybookComponent, ...]:
        return (LabelledComponent("earlier"), OtherKindComponent("earlier"))


class LaterContribution(PackageContribution):
    """
    A contribution registered under the entry point name sorting last.
    """

    @classproperty
    def playbook_components(cls) -> tuple[PlaybookComponent, ...]:
        return (LabelledComponent("later"),)


# %% setup steps


@dataclass(frozen=True)
class TitledStep(SetupStep):
    """
    A setup step whose title is given.
    """

    step_title: str
    """
    What the step changes.
    """

    @property
    def title(self) -> str:
        return self.step_title

    @property
    def reason(self) -> str:
        return "It is needed."

    def instructions(self) -> list[str]:
        return ["Do it."]


@dataclass(frozen=True)
class StepsNamingTheCheckout(SetupSteps):
    """
    Setup steps titled after the repository checkout they are worked out for.
    """

    prefix: str
    """
    What every step's title starts with.
    """

    def steps_for_repository_checkout(
        self, repository_checkout: RepositoryCheckout
    ) -> tuple[SetupStep, ...]:
        return (TitledStep(f"{self.prefix} {repository_checkout.working_tree.name}"),)


# %% skills


@dataclass(frozen=True)
class DeclaredSkill(Skill):
    """
    The skill the dataset plugin ships a body for.
    """

    @classproperty
    def description(cls) -> str:
        return "Use when a test needs a skill the plugin ships."

    @classproperty
    def allowed_tools(cls) -> tuple[SessionTool, ...]:
        return (BuiltInTool.RUN_SHELL_COMMAND, BuiltInTool.READ_FILE)


@dataclass(frozen=True)
class UnshippedSkill(Skill):
    """
    A skill the dataset plugin ships no instructions for.
    """

    @classproperty
    def description(cls) -> str:
        return "Use when a test needs a skill the plugin lacks."

    @classproperty
    def allowed_tools(cls) -> tuple[SessionTool, ...]:
        return ()


@dataclass(frozen=True)
class CheckCIStatusSkill(Skill):
    """
    A skill whose class name holds an acronym.
    """

    @classproperty
    def description(cls) -> str:
        return "Use when a test needs a name with an acronym in it."

    @classproperty
    def allowed_tools(cls) -> tuple[SessionTool, ...]:
        return ()
