"""
What basstler-reviews adds to the default playbook.
"""

from __future__ import annotations

from dataclasses import dataclass

from basstler.class_property import classproperty
from basstler.playbook.component import PlaybookComponent
from basstler.playbook.contribution import PackageContribution
from basstler.playbook.skill import Skill
from basstler.session_tool import SessionTool

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
            SessionTool.RUN_SHELL_COMMAND,
            SessionTool.READ_FILE,
            SessionTool.RUN_SKILL,
            SessionTool.ATTACH_REPOSITORY,
            SessionTool.CREATE_SESSION,
            SessionTool.READ_SESSION,
            SessionTool.LIST_SESSION_EVENTS,
            SessionTool.ARCHIVE_SESSION,
        )


# %% contribution


class ReviewsContribution(PackageContribution):
    """
    The skill that reads a branch's upstream review threads and checks.
    """

    @classproperty
    def playbook_components(cls) -> tuple[PlaybookComponent, ...]:
        return (UpstreamReviewsSkill(),)
