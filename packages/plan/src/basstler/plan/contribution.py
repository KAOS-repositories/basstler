"""
What basstler-plan adds to the default playbook.
"""

from __future__ import annotations

from dataclasses import dataclass

from basstler.class_property import classproperty
from basstler.plan.handover_command import plan_handover_app
from basstler.plan.repository_rules_command import repository_rules_app
from basstler.playbook.command_group import CommandGroup
from basstler.playbook.component import PlaybookComponent
from basstler.playbook.contribution import PackageContribution
from basstler.playbook.skill import Skill
from basstler.session_tool import SessionTool

# %% skills


@dataclass(frozen=True)
class AddPlanItemSkill(Skill):
    """
    The ``/add-plan-item`` skill.
    """

    @classproperty
    def description(cls) -> str:
        return (
            "Decide where new work belongs - folded into an unlanded item, a new "
            "item, a new plan, or untracked - and propose it via plan mode "
            'without writing code. Invoke as "/add-plan-item {description of the '
            'work}". Use when asked where new work goes, to add a plan item, or '
            "whether it should be its own PR."
        )

    @classproperty
    def allowed_tools(cls) -> tuple[SessionTool, ...]:
        return (
            SessionTool.RUN_SHELL_COMMAND,
            SessionTool.READ_FILE,
            SessionTool.SEARCH_FILE_CONTENTS,
            SessionTool.FIND_FILES,
            SessionTool.ASK_USER,
            SessionTool.RUN_SKILL,
            SessionTool.ENTER_PLAN_MODE,
            SessionTool.EXIT_PLAN_MODE,
            SessionTool.LIST_PULL_REQUESTS,
            SessionTool.READ_PULL_REQUEST,
            SessionTool.READ_REPOSITORY_FILE,
            SessionTool.READ_ISSUE,
            SessionTool.SUBSCRIBE_PULL_REQUEST_ACTIVITY,
        )


@dataclass(frozen=True)
class PlanCreateSkill(Skill):
    """
    The ``/plan-create`` skill.
    """

    @classproperty
    def description(cls) -> str:
        return (
            "Create a multi-PR plan on the personal-notes branch, or migrate a "
            "roadmap doc into one, which publishes its page on the plan site. "
            'Invoke as "/plan-create {plan-id}". Use when asked to start tracking'
            " work as a plan."
        )

    @classproperty
    def allowed_tools(cls) -> tuple[SessionTool, ...]:
        return (
            SessionTool.RUN_SHELL_COMMAND,
            SessionTool.READ_FILE,
            SessionTool.WRITE_FILE,
            SessionTool.SEARCH_FILE_CONTENTS,
            SessionTool.FIND_FILES,
            SessionTool.ASK_USER,
            SessionTool.RUN_SKILL,
            SessionTool.LIST_PULL_REQUESTS,
            SessionTool.READ_PULL_REQUEST,
            SessionTool.WRITE_ISSUE,
            SessionTool.CREATE_PULL_REQUEST,
            SessionTool.SUBSCRIBE_PULL_REQUEST_ACTIVITY,
        )


@dataclass(frozen=True)
class PlanItemKickoffSkill(Skill):
    """
    The ``/plan-item-kickoff`` skill.
    """

    @classproperty
    def description(cls) -> str:
        return (
            "Start one tracked plan item: gather its context, open its branch and"
            " draft PR, record it, then plan or implement per the execution mode."
            ' Invoke as "/plan-item-kickoff {plan-id} {item-id}". Use from a plan'
            ' page\'s "Start now" link or when asked to start or kick off an item.'
        )

    @classproperty
    def allowed_tools(cls) -> tuple[SessionTool, ...]:
        return (
            SessionTool.RUN_SHELL_COMMAND,
            SessionTool.READ_FILE,
            SessionTool.SEARCH_FILE_CONTENTS,
            SessionTool.FIND_FILES,
            SessionTool.EDIT_FILE,
            SessionTool.WRITE_FILE,
            SessionTool.ASK_USER,
            SessionTool.RUN_SKILL,
            SessionTool.ENTER_PLAN_MODE,
            SessionTool.EXIT_PLAN_MODE,
            SessionTool.LIST_PULL_REQUESTS,
            SessionTool.READ_PULL_REQUEST,
            SessionTool.READ_REPOSITORY_FILE,
            SessionTool.CREATE_PULL_REQUEST,
            SessionTool.UPDATE_PULL_REQUEST,
            SessionTool.SUBSCRIBE_PULL_REQUEST_ACTIVITY,
            SessionTool.READ_ISSUE,
        )


@dataclass(frozen=True)
class PlanItemModeSkill(Skill):
    """
    The ``/plan-item-mode`` skill.
    """

    @classproperty
    def description(cls) -> str:
        return (
            "Pin whether kickoff and resolve implement directly (auto), present a"
            " plan first (plan), or ask each time (ask). Invoke as "
            '"/plan-item-mode {auto|plan|ask} [kickoff|resolve|both]". Use when '
            "the user states a standing preference about being asked."
        )

    @classproperty
    def allowed_tools(cls) -> tuple[SessionTool, ...]:
        return (
            SessionTool.RUN_SHELL_COMMAND,
            SessionTool.READ_FILE,
        )


@dataclass(frozen=True)
class PlanItemResolveSkill(Skill):
    """
    The ``/plan-item-resolve`` skill.
    """

    @classproperty
    def description(cls) -> str:
        return (
            "Resolve what stalls an underway plan item - conflicts, CI, review "
            "threads, tracking-issue discussion - on its existing branch, per the"
            ' execution mode. Invoke as "/plan-item-resolve {plan-id} {item-id}" '
            'or "/plan-item-resolve {pull-request-number}". Use from a plan '
            "page's Resolve/Resume/Reconsider link or when asked to resolve, "
            "unblock or resume an item."
        )

    @classproperty
    def allowed_tools(cls) -> tuple[SessionTool, ...]:
        return (
            SessionTool.RUN_SHELL_COMMAND,
            SessionTool.READ_FILE,
            SessionTool.SEARCH_FILE_CONTENTS,
            SessionTool.FIND_FILES,
            SessionTool.EDIT_FILE,
            SessionTool.WRITE_FILE,
            SessionTool.ASK_USER,
            SessionTool.RUN_SKILL,
            SessionTool.ENTER_PLAN_MODE,
            SessionTool.EXIT_PLAN_MODE,
            SessionTool.LIST_PULL_REQUESTS,
            SessionTool.READ_PULL_REQUEST,
            SessionTool.READ_ISSUE,
            SessionTool.READ_REPOSITORY_FILE,
            SessionTool.UPDATE_PULL_REQUEST,
            SessionTool.SUBSCRIBE_PULL_REQUEST_ACTIVITY,
        )


@dataclass(frozen=True)
class PlanRecommendModelsSkill(Skill):
    """
    The ``/plan-recommend-models`` skill.
    """

    @classproperty
    def description(cls) -> str:
        return (
            "Judge and set the recommended model (opus, sonnet or haiku) of plan "
            'items by task difficulty. Invoke as "/plan-recommend-models '
            '{plan-id} [{item-id}...]". Use when session start lists items '
            "without a recommended model, and from plan-create and add-plan-item "
            "when they add items."
        )

    @classproperty
    def allowed_tools(cls) -> tuple[SessionTool, ...]:
        return (
            SessionTool.RUN_SHELL_COMMAND,
            SessionTool.READ_FILE,
        )


# %% contribution


class PlanContribution(PackageContribution):
    """
    The plan commands and the skills that create and work plans.
    """

    @classproperty
    def playbook_components(cls) -> tuple[PlaybookComponent, ...]:
        return (
            CommandGroup(plan_handover_app),
            CommandGroup(repository_rules_app),
            AddPlanItemSkill(),
            PlanCreateSkill(),
            PlanItemKickoffSkill(),
            PlanItemModeSkill(),
            PlanItemResolveSkill(),
            PlanRecommendModelsSkill(),
        )
