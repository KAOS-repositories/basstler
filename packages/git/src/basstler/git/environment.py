"""
The environment variables the git commands set.
"""

from __future__ import annotations

from basstler.environment import EnvironmentVariable


class GitVariable(EnvironmentVariable):
    """
    The variables git reads that this package, or its tests, set for the commands run.
    """

    INDEX_FILE = "GIT_INDEX_FILE"
    """
    The index git stages into, in place of the clone's own.
    """

    CONFIGURATION_COUNT = "GIT_CONFIG_COUNT"
    """
    How many configuration entries the environment passes to git.
    """

    CONFIGURATION_KEY_PREFIX = "GIT_CONFIG_KEY_"
    """
    Followed by an entry's index, names the variable holding that entry's key.
    """

    CONFIGURATION_VALUE_PREFIX = "GIT_CONFIG_VALUE_"
    """
    Followed by an entry's index, names the variable holding that entry's value.
    """

    COMMITTER_DATE = "GIT_COMMITTER_DATE"
    """
    The date git records as a new commit's committer date, in place of the clock's.
    """
