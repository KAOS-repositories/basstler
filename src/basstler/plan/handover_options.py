"""
The options of the ``basstler plan-handover`` commands that their messages name.
"""

from __future__ import annotations

from enum import StrEnum

# %% the options


class PlanHandoverOption(StrEnum):
    """
    An option of a ``basstler plan-handover`` command.
    """

    PULL_REQUEST = "--pull-request"
    """
    The number of the one handover pull request an import takes over.
    """

    ALL = "--all"
    """
    Take over every handover pull request open on the repository.
    """
