"""
What basstler-stack adds to the default playbook.
"""

from __future__ import annotations

from dataclasses import dataclass

from basstler.class_property import classproperty
from basstler.playbook.component import PlaybookComponent
from basstler.playbook.contribution import PackageContribution
from basstler.playbook.skill import Skill
from basstler.session_tool import BuiltInTool, GitHubTool, SessionTool

# %% skills


@dataclass(frozen=True)
class StackedPRMaintenanceSkill(Skill):
    """
    The ``/stacked-pr-maintenance`` skill.
    """

    @classproperty
    def description(cls) -> str:
        return (
            "Run one maintenance pass over a fork's stacked pull requests, or "
            "over one branch's stack: reparent, restack, and promote approved "
            'branches upstream. Invoke as "/stacked-pr-maintenance '
            '[fork={owner/repo}] [upstream={owner/repo}] [stacked-on={branch}]". '
            "Use when asked to restack or promote the stack, and as the first "
            "step of plan-item-kickoff and plan-item-resolve."
        )

    @classproperty
    def allowed_tools(cls) -> tuple[SessionTool, ...]:
        return (
            BuiltInTool.RUN_SHELL_COMMAND,
            BuiltInTool.READ_FILE,
            BuiltInTool.WRITE_FILE,
            BuiltInTool.ASK_USER,
            GitHubTool.UPDATE_PULL_REQUEST,
        )


# %% contribution


class StackContribution(PackageContribution):
    """
    The skill that maintains stacked pull requests.
    """

    @classproperty
    def playbook_components(cls) -> tuple[PlaybookComponent, ...]:
        return (StackedPRMaintenanceSkill(),)
