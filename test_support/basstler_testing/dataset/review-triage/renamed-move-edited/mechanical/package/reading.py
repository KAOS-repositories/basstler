"""
How the rows of a store are read.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from package.limits import ROW_LIMIT
from package.sessions import SessionKey


@dataclass
class Reader:
    """
    Reads the rows of a store, once per session.
    """

    session: dict[str, Any]
    """
    The session's state.
    """

    def read(self, rows: list[Any]) -> list[Any]:
        """
        :param rows: The rows of a store.
        :return: The rows, unless the session already loaded them.
        """
        if self.session.get(SessionKey.LOADED, False):
            return []
        self.session[SessionKey.LOADED] = True
        return rows[:ROW_LIMIT]
