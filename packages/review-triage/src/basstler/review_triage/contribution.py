"""
What basstler-review-triage adds to the default playbook.
"""

from __future__ import annotations

from enum import StrEnum

import basstler.review_triage.stop_hook
from basstler.class_property import classproperty
from basstler.playbook.command_group import CommandGroup
from basstler.playbook.component import PlaybookComponent
from basstler.playbook.contribution import PackageContribution
from basstler.playbook.plugin import (
    HookDefinition,
    HookEvent,
    PackageModuleCommand,
    SkillDefinition,
)
from basstler.review_triage.command_line import review_triage_app


class ReviewTriageSkill(StrEnum):
    """
    The plugin skills basstler-review-triage ships, by name.
    """

    SETUP_REVIEW_TRIAGE = "setup-review-triage"
    """
    Sets up marking a pull request's mechanical files viewed.
    """


class ReviewTriageContribution(PackageContribution):
    """
    The ``basstler review-triage`` commands, their setup skill and the hook that marks
    files viewed when a turn ends.
    """

    @classproperty
    def components(cls) -> tuple[PlaybookComponent, ...]:
        return (
            CommandGroup(review_triage_app),
            *(SkillDefinition(skill) for skill in ReviewTriageSkill),
            HookDefinition(
                HookEvent.STOP, PackageModuleCommand(basstler.review_triage.stop_hook)
            ),
        )
