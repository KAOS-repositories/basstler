"""
What basstler-stack adds to the default playbook.
"""

from __future__ import annotations

from enum import StrEnum

from basstler.class_property import classproperty
from basstler.playbook.component import PlaybookComponent
from basstler.playbook.contribution import PackageContribution
from basstler.playbook.plugin import SkillDefinition


class StackSkill(StrEnum):
    """
    The plugin skills basstler-stack ships, by name.
    """

    STACKED_PULL_REQUEST_MAINTENANCE = "stacked-pr-maintenance"
    """
    One maintenance pass over a fork's stacked pull requests.
    """


class StackContribution(PackageContribution):
    """
    The skill that maintains stacked pull requests.
    """

    @classproperty
    def playbook_components(cls) -> tuple[PlaybookComponent, ...]:
        return tuple(SkillDefinition(skill) for skill in StackSkill)
