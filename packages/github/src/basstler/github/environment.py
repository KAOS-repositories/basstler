"""
The environment variables the GitHub client reads.
"""

from __future__ import annotations

from basstler.environment import GitHubActionsRunnerVariable


class GitHubActionsOutputVariable(GitHubActionsRunnerVariable):
    """
    The runner's variable naming the file a step's outputs go to.
    """

    OUTPUT = "GITHUB_OUTPUT"
    """
    The file a step appends its ``<key>=<value>`` outputs to.
    """
