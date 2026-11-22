"""
What basstler-notes adds to the default playbook.
"""

from __future__ import annotations

from enum import StrEnum

from basstler.class_property import classproperty
from basstler.locations import PluginLocation
from basstler.playbook.component import PlaybookComponent
from basstler.playbook.contribution import PackageContribution
from basstler.playbook.plugin import (
    HookDefinition,
    HookEvent,
    PluginScriptCommand,
    SkillDefinition,
)
from basstler.setup.steps import ForkSetupSteps


class NotesSkill(StrEnum):
    """
    The plugin skills basstler-notes ships, by name.
    """

    SETUP_PERSONAL_NOTES = "setup-personal-notes"
    """
    The one-time setup of the personal-notes branch.
    """


class NotesContribution(PackageContribution):
    """
    The session-start hook that loads the personal notes, their setup skill and the
    setup steps left to the user.
    """

    @classproperty
    def components(cls) -> tuple[PlaybookComponent, ...]:
        return (
            *(SkillDefinition(skill) for skill in NotesSkill),
            HookDefinition(
                HookEvent.SESSION_START,
                PluginScriptCommand(PluginLocation.SESSION_START_SCRIPT),
            ),
            ForkSetupSteps(),
        )
