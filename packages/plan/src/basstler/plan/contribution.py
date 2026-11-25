"""
What basstler-plan adds to the default playbook.
"""

from __future__ import annotations

import basstler.plan.agentic_loop.stop_hook
from basstler.class_property import classproperty
from basstler.plan.agentic_loop.command_line import agentic_loop_app
from basstler.plan.handover_command import plan_handover_app
from basstler.plan.repository_rules_command import repository_rules_app
from basstler.plan.skills import (
    AddPlanItemSkill,
    PlanCreateSkill,
    PlanItemKickoffSkill,
    PlanItemLoopSkill,
    PlanItemModeSkill,
    PlanItemResolveSkill,
    PlanItemReviewSkill,
    PlanRecommendModelsSkill,
)
from basstler.playbook.command_group import CommandGroup
from basstler.playbook.component import PlaybookComponent
from basstler.playbook.contribution import PackageContribution
from basstler.playbook.plugin import PackageModuleCommand, StopHook

# %% contribution


class PlanContribution(PackageContribution):
    """
    The plan commands, the skills that create and work plans, and the hook that starts
    an agentic loop's next session.
    """

    @classproperty
    def playbook_components(cls) -> tuple[PlaybookComponent, ...]:
        return (
            CommandGroup(plan_handover_app),
            CommandGroup(repository_rules_app),
            CommandGroup(agentic_loop_app),
            AddPlanItemSkill(),
            PlanCreateSkill(),
            PlanItemKickoffSkill(),
            PlanItemLoopSkill(),
            PlanItemModeSkill(),
            PlanItemResolveSkill(),
            PlanItemReviewSkill(),
            PlanRecommendModelsSkill(),
            StopHook(PackageModuleCommand(basstler.plan.agentic_loop.stop_hook)),
        )
