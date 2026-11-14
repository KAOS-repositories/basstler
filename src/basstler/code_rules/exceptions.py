"""
The errors raised while checking and fixing code against the rules.
"""

from __future__ import annotations

from dataclasses import dataclass

from basstler.exceptions import DataclassException


@dataclass
class FixDoesNotConvergeError(DataclassException, RuntimeError):
    """
    Raised when applying fixes leaves at least as many places breaking rules as there
    were before, so fixing again would never end.
    """

    lines: tuple[int, ...]
    """
    The first line of each place still breaking a rule, counting from one.
    """

    def error_message(self) -> str:
        return (
            f"fixing left {len(self.lines)} places breaking a rule, no fewer than "
            f"before, on lines {', '.join(map(str, self.lines))}"
        )

    def suggest_correction(self) -> str:
        return (
            "A fix whose replacement still breaks its rule needs correcting; its "
            "examples' tests show which."
        )
