"""
The environment variables the upstream review reader reads.
"""

from __future__ import annotations

from basstler.environment import EnvironmentVariable


class UpstreamReviewsClaudeCodeVariable(EnvironmentVariable):
    """
    The variables Claude Code sets that locate the session's transcript.
    """

    SESSION_IDENTIFIER = "CLAUDE_CODE_SESSION_ID"
    """
    The session's own identifier, which names its transcript file.
    """

    CONFIGURATION_DIRECTORY = "CLAUDE_CONFIG_DIR"
    """
    Where Claude Code keeps its state, transcripts included, when not ``~/.claude``.
    """


class UpstreamReviewsGitHubActionsVariable(EnvironmentVariable):
    """
    The variables a GitHub Actions runner sets that the upstream review Action reads.
    """

    REPOSITORY_OWNER = "GITHUB_REPOSITORY_OWNER"
    """
    The owner of the repository the workflow runs in.
    """
