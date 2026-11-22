"""
The names of the ``basstler code-rules`` commands.
"""

from __future__ import annotations


from basstler.basstler_command import BasstlerCommand
from basstler.class_property import classproperty


class CodeRulesCommand(BasstlerCommand):
    """
    The ``basstler code-rules`` command group and its commands, by name.
    """

    @classproperty
    def group(cls) -> str:
        return "code-rules"

    CHECK = "check"
    """
    Report the code that breaks a rule a checker enforces.
    """
    FIX = "fix"
    """
    Apply the fix of every rule that has one.
    """
    NEW_CROSSINGS = "new-crossings"
    """
    Report the boundary crossings a base commit does not have.
    """
    AGENTS_MD = "agents-md"
    """
    Generate the repository's ``AGENTS.md`` from its rules.
    """
