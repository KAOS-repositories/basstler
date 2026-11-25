"""
The rules of the review triage, and how a project and the command line choose them.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from pydantic import Field

from basstler.json_model import ValidatedJSONModel
from basstler.locations import ProjectLocation

# %% the rules


class TriageRule(StrEnum):
    """
    A rule widening what the triage counts as mechanical.
    """

    MODULE_DOCUMENTATION = "module-documentation"
    """
    Any change to the documentation at the top of a module is mechanical.
    """

    DOCSTRINGS_ADDED_OR_REMOVED = "docstrings-added-or-removed"
    """
    A docstring a function, class or field gains or loses is mechanical.
    """

    TEST_DOCSTRINGS_ADDED_OR_REMOVED = "test-docstrings-added-or-removed"
    """
    A docstring a function, class or field of a test file gains or loses is mechanical.
    """


DEFAULT_RULES = frozenset(
    {TriageRule.MODULE_DOCUMENTATION, TriageRule.TEST_DOCSTRINGS_ADDED_OR_REMOVED}
)
"""
The rules on unless a project or the command line turns them off.
"""


# %% choosing rules


@dataclass(frozen=True)
class RuleSelection:
    """
    Rules chosen on or off, the way a project's settings or the command line choose them.
    """

    select: frozenset[TriageRule] = frozenset()
    """
    The rules turned on.
    """

    ignore: frozenset[TriageRule] = frozenset()
    """
    The rules turned off, outranking :attr:`select`.
    """

    @property
    def enabled(self) -> frozenset[TriageRule]:
        """
        The rules left on, the default rules among them unless ignored.
        """
        return (DEFAULT_RULES | self.select) - self.ignore

    def applied_to(self, base: RuleSelection) -> frozenset[TriageRule]:
        """
        :param base: The choice this one adjusts, such as the project's.
        :return: The rules on once this choice is applied over *base*.
        """
        return (base.enabled | self.select) - self.ignore


# %% a project's settings


class ReviewTriageSettings(ValidatedJSONModel):
    """
    The ``[tool.basstler.review-triage]`` table of a project's ``pyproject.toml``.
    """

    select: tuple[TriageRule, ...] = ()
    """
    The rules the project turns on.
    """

    ignore: tuple[TriageRule, ...] = ()
    """
    The rules the project turns off.
    """

    @property
    def selection(self) -> RuleSelection:
        """
        The project's choice of rules.
        """
        return RuleSelection(frozenset(self.select), frozenset(self.ignore))

    @classmethod
    def from_checkout(cls, root: Path) -> ReviewTriageSettings:
        """
        :param root: A checkout's root directory.
        :return: Its settings, those of a project choosing nothing when it has no
            ``pyproject.toml`` or no such table.
        :raises pydantic.ValidationError: If the table names a rule that does not exist.
        """
        pyproject = root / ProjectLocation.PYPROJECT
        if not pyproject.is_file():
            return cls()
        return ProjectMetadata.from_json(
            tomllib.loads(pyproject.read_text(encoding="utf-8"))
        ).tool.basstler.review_triage


class BasstlerTools(ValidatedJSONModel):
    """
    The ``[tool.basstler]`` table of a ``pyproject.toml``.
    """

    review_triage: ReviewTriageSettings = Field(
        default_factory=ReviewTriageSettings, alias="review-triage"
    )
    """
    The settings of the review triage.
    """


class ProjectTools(ValidatedJSONModel):
    """
    The ``[tool]`` table of a ``pyproject.toml``.
    """

    basstler: BasstlerTools = Field(default_factory=BasstlerTools)
    """
    This package's settings.
    """


class ProjectMetadata(ValidatedJSONModel):
    """
    A project's ``pyproject.toml``, read only as far as this package's settings.
    """

    tool: ProjectTools = Field(default_factory=ProjectTools)
    """
    The tools' settings.
    """
