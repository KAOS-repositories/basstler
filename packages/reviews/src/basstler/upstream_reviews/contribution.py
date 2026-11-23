"""
What basstler-reviews adds to the default playbook.
"""

from __future__ import annotations

from dataclasses import dataclass

from basstler.class_property import classproperty
from basstler.playbook.component import PlaybookComponent
from basstler.playbook.contribution import PackageContribution
from basstler.playbook.skill import Skill
from basstler.session_tool import BuiltInTool, CloudSessionTool, SessionTool

# %% skills


@dataclass(frozen=True)
class UpstreamReviewsSkill(Skill):
    """
    The ``/upstream-reviews`` skill.
    """

    @classproperty
    def description(cls) -> str:
        return (
            "Report a fork branch's upstream pull request: its CI checks, failure"
            ' logs and unresolved review threads. Invoke as "/upstream-reviews '
            '[{pull-request-number}|{branch}]". Use when asked what upstream '
            "reviewers or CI said about a promoted branch."
        )

    @classproperty
    def allowed_tools(cls) -> tuple[SessionTool, ...]:
        return (
            BuiltInTool.RUN_SHELL_COMMAND,
            BuiltInTool.READ_FILE,
            BuiltInTool.RUN_SKILL,
            CloudSessionTool.ATTACH_REPOSITORY,
            CloudSessionTool.CREATE_SESSION,
            CloudSessionTool.READ_SESSION,
            CloudSessionTool.LIST_SESSION_EVENTS,
            CloudSessionTool.ARCHIVE_SESSION,
        )


# %% contribution


class ReviewsContribution(PackageContribution):
    """
    The skill that reads a branch's upstream review threads and checks.
    """

    @classproperty
    def playbook_components(cls) -> tuple[PlaybookComponent, ...]:
        return (UpstreamReviewsSkill(),)
