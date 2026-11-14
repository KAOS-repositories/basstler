"""
The errors raised while applying an action to a module.
"""

from __future__ import annotations

from dataclasses import dataclass

from libcst.metadata import CodeRange

from basstler.exceptions import DataclassException


@dataclass
class ActionTargetMissingError(DataclassException, LookupError):
    """
    Raised when the module an action is applied to has no node where the action expects
    the node it changes.
    """

    location: CodeRange
    """
    Where the action expected the node.
    """

    node_type: str
    """
    The name of the expected node's type.
    """

    def error_message(self) -> str:
        start, end = self.location.start, self.location.end
        return (
            f"no {self.node_type} from {start.line}:{start.column} to "
            f"{end.line}:{end.column} matches the node the action changes"
        )

    def suggest_correction(self) -> str:
        return (
            "Apply the action to the module it was made for, or to the module the "
            "action before it in its plan produced."
        )
