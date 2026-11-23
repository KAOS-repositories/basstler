"""
The environment variables the upstream review reader reads.
"""

from __future__ import annotations

from basstler.environment import EnvironmentVariable


class UpstreamReviewsGitHubActionsVariable(EnvironmentVariable):
    """
    The variables a GitHub Actions runner sets that the upstream review Action reads.
    """

    REPOSITORY_OWNER = "GITHUB_REPOSITORY_OWNER"
    """
    The owner of the repository the workflow runs in.
    """
