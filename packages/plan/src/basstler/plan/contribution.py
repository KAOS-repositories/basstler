"""
What basstler-plan adds to the default playbook.
"""

from __future__ import annotations

from enum import StrEnum

from basstler.class_property import classproperty
from basstler.plan.handover_command import plan_handover_app
from basstler.plan.repository_rules_command import repository_rules_app
from basstler.playbook.command_group import CommandGroup
from basstler.playbook.component import PlaybookComponent
from basstler.playbook.contribution import PackageContribution
from basstler.playbook.plugin import SkillDefinition


class PlanSkill(StrEnum):
    """
    The plugin skills basstler-plan ships, by name.
    """

    ADD_PLAN_ITEM = "add-plan-item"
    """
    Decides where new work belongs and proposes it.
    """

    PLAN_CREATE = "plan-create"
    """
    Creates a multi-pull-request plan.
    """

    PLAN_ITEM_KICKOFF = "plan-item-kickoff"
    """
    Starts one plan item.
    """

    PLAN_ITEM_MODE = "plan-item-mode"
    """
    Pins how kickoff and resolve work an item.
    """

    PLAN_ITEM_RESOLVE = "plan-item-resolve"
    """
    Resolves what stalls an item underway.
    """

    PLAN_RECOMMEND_MODELS = "plan-recommend-models"
    """
    Sets the model recommended for each item.
    """


class PlanContribution(PackageContribution):
    """
    The plan commands and the skills that create and work plans.
    """

    @classproperty
    def components(cls) -> tuple[PlaybookComponent, ...]:
        return (
            CommandGroup(plan_handover_app),
            CommandGroup(repository_rules_app),
            *(SkillDefinition(skill) for skill in PlanSkill),
        )
