"""
The failures the receiver inference experiment reports.
"""

from __future__ import annotations

from dataclasses import dataclass

from basstler.exceptions import DataclassException


@dataclass
class ReceiversNotProbed(DataclassException, RuntimeError):
    """
    Raised when a triage asks about receivers no type checker was asked for, so a
    checker's result would count them unanswered.
    """

    pull_request: str
    """
    The pull request triaged, as ``owner/name#number``.
    """

    receivers: tuple[str, ...]
    """
    Each receiver not probed, as ``path:line: source``.
    """

    def error_message(self) -> str:
        listed = "\n".join(self.receivers)
        return f"the triage of {self.pull_request} asked about unprobed receivers:\n{listed}"

    def suggest_correction(self) -> str:
        return (
            "make ReceiverQuestion.from_method_calls find every receiver the triage "
            "asks about"
        )
