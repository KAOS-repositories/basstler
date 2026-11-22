"""
The jobs and steps of this repository's publish workflow that its tests refer to.
"""

from __future__ import annotations

from enum import StrEnum

# %% names in the workflow


class PublishJobName(StrEnum):
    """
    The jobs of this repository's publish workflow.
    """

    BUILD = "build"
    PUBLISH = "publish-pypi"


class PublishStepId(StrEnum):
    """
    The steps of this repository's publish workflow that its tests run.
    """

    LIST_DISTRIBUTIONS = "distributions"
    KEEP_OWN_FILES = "files"
