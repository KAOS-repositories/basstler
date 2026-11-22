"""
What basstler-reviews adds to the default playbook.
"""

from __future__ import annotations

from enum import StrEnum

from basstler.class_property import classproperty
from basstler.playbook.component import PlaybookComponent
from basstler.playbook.contribution import PackageContribution
from basstler.playbook.plugin import SkillDefinition


class ReviewsSkill(StrEnum):
    """
    The plugin skills basstler-reviews ships, by name.
    """

    UPSTREAM_REVIEWS = "upstream-reviews"
    """
    Reports a fork branch's upstream pull request.
    """


class ReviewsContribution(PackageContribution):
    """
    The skill that reads a branch's upstream review threads and checks.
    """

    @classproperty
    def playbook_components(cls) -> tuple[PlaybookComponent, ...]:
        return tuple(SkillDefinition(skill) for skill in ReviewsSkill)
