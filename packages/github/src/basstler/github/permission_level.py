"""
How much of a repository's resource an account or a token may use.
"""

from __future__ import annotations

from enum import StrEnum

# %% the level


class PermissionLevel(StrEnum):
    """
    The access a permission grants on one of a repository's resources.
    """

    READ = "read"
    """
    Read only.
    """

    WRITE = "write"
    """
    Read and write.
    """

    @classmethod
    def broadest(cls, levels: list[PermissionLevel]) -> PermissionLevel:
        """
        :param levels: The levels several jobs need on one permission, at least one.
        :return: The level that grants all of them.
        """
        return cls.WRITE if cls.WRITE in levels else cls.READ
