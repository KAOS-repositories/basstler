"""
What basstler-review-triage adds to the default playbook.
"""

from __future__ import annotations

from dataclasses import dataclass

import basstler.review_triage.stop_hook
from basstler.class_property import classproperty
from basstler.playbook.command_group import CommandGroup
from basstler.playbook.component import PlaybookComponent
from basstler.playbook.contribution import PackageContribution
from basstler.playbook.plugin import (
    PackageModuleCommand,
    StopHook,
)
from basstler.playbook.skill import Skill
from basstler.review_triage.command_line import review_triage_app
from basstler.session_tool import SessionTool

# %% skills


@dataclass(frozen=True)
class SetupReviewTriageSkill(Skill):
    """
    The ``/setup-review-triage`` skill.
    """

    @classproperty
    def title(cls) -> str:
        """
        :attr:`Skill.title`, worded as the imperative it is.
        """
        return "Set up the review triage's marking of files viewed"

    @classproperty
    def description(cls) -> str:
        return (
            "Set up marking a pull request's mechanical files viewed, from the "
            "user's own computer or from a repository's Actions, and walk the "
            "user through the steps only they can take. Invoke as "
            '"/setup-review-triage". Use when the user wants `basstler '
            "review-triage mark-viewed` to work, or when it failed."
        )

    @classproperty
    def allowed_tools(cls) -> tuple[SessionTool, ...]:
        return (
            SessionTool.RUN_SHELL_COMMAND,
            SessionTool.READ_FILE,
            SessionTool.ASK_USER,
        )


# %% contribution


class ReviewTriageContribution(PackageContribution):
    """
    The ``basstler review-triage`` commands, their setup skill and the hook that marks
    files viewed when a turn ends.
    """

    @classproperty
    def playbook_components(cls) -> tuple[PlaybookComponent, ...]:
        return (
            CommandGroup(review_triage_app),
            SetupReviewTriageSkill(),
            StopHook(PackageModuleCommand(basstler.review_triage.stop_hook)),
        )
