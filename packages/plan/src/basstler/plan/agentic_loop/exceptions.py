"""
The failures of starting an agentic loop's next session.
"""

from __future__ import annotations

from dataclasses import dataclass

from basstler.exceptions import DataclassException


@dataclass
class ClaudeCodeMissingError(DataclassException, FileNotFoundError):
    """
    Raised when the next session is to start on this machine, but no Claude Code command
    is on the executable search path.
    """

    executable: str
    """
    The command that was looked for.
    """

    def error_message(self) -> str:
        return f"the agentic loop found no {self.executable!r} command to start the next session with"

    def suggest_correction(self) -> str:
        return (
            "Install Claude Code's command line, or turn the loop off with "
            "/plan-item-loop off."
        )
