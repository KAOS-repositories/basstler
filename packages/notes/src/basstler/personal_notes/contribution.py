"""
What basstler-notes adds to the default playbook.
"""

from __future__ import annotations

from dataclasses import dataclass

from basstler.class_property import classproperty
from basstler.locations import PluginLocation
from basstler.playbook.component import PlaybookComponent
from basstler.playbook.contribution import PackageContribution
from basstler.playbook.plugin import (
    PluginScriptCommand,
    SessionStartHook,
)
from basstler.playbook.skill import Skill
from basstler.session_tool import BuiltInTool, GitHubTool, SessionTool
from basstler.setup.steps import ForkSetupSteps

# %% skills


@dataclass(frozen=True)
class SetupPersonalNotesSkill(Skill):
    """
    The ``/setup-personal-notes`` skill.
    """

    @classproperty
    def title(cls) -> str:
        """
        :attr:`Skill.title`, worded as the imperative it is.
        """
        return "Set up personal notes"

    @classproperty
    def description(cls) -> str:
        return (
            "One-time setup of the personal-notes branch, its configuration and "
            'the package\'s dependencies. Invoke as "/setup-personal-notes". Use '
            "on first setup, or when personal notes, PR progress or plans are not"
            " working."
        )

    @classproperty
    def allowed_tools(cls) -> tuple[SessionTool, ...]:
        return (
            BuiltInTool.RUN_SHELL_COMMAND,
            BuiltInTool.READ_FILE,
            BuiltInTool.WRITE_FILE,
            BuiltInTool.ASK_USER,
            GitHubTool.READ_GITHUB_USER,
            GitHubTool.READ_LABEL,
            GitHubTool.LIST_ACTIONS,
            GitHubTool.READ_JOB_LOGS,
        )


# %% contribution


class NotesContribution(PackageContribution):
    """
    The session-start hook that loads the personal notes, their setup skill and the
    setup steps left to the user.
    """

    @classproperty
    def playbook_components(cls) -> tuple[PlaybookComponent, ...]:
        return (
            SetupPersonalNotesSkill(),
            SessionStartHook(PluginScriptCommand(PluginLocation.SESSION_START_SCRIPT)),
            ForkSetupSteps(),
        )
