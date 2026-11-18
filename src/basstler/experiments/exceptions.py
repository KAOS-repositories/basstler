"""
The failures the experiments report.
"""

from __future__ import annotations

from dataclasses import dataclass

from basstler.exceptions import DataclassException


@dataclass
class ExperimentCommandFailed(DataclassException, RuntimeError):
    """
    Raised when a command an experiment needs, such as installing a tool, fails.
    """

    command: tuple[str, ...]
    """
    The command and its arguments.
    """

    exit_status: int
    """
    The status it exited with.
    """

    output: str
    """
    What it wrote to its standard output and error.
    """

    def error_message(self) -> str:
        return (
            f"`{' '.join(self.command)}` exited with status {self.exit_status}:\n"
            f"{self.output}"
        )

    def suggest_correction(self) -> str:
        return "fix what the output names, then run the experiment again"
