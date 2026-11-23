"""
The environment variables the upstream review reader reads.
"""

from __future__ import annotations

from basstler.environment import GitHubActionsRunnerVariable


class UpstreamReviewsGitHubActionsVariable(GitHubActionsRunnerVariable):
    """
    The runner's variables the upstream review Action reads.
    """

    REPOSITORY_OWNER = "GITHUB_REPOSITORY_OWNER"
    """
    The owner of the repository the workflow runs in.
    """
