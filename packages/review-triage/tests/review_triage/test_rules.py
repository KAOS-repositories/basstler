"""
Choosing which rules a triage applies: the project's settings and the options.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from basstler.review_triage.command_line import TriagePublication
from basstler.review_triage.declaration import TriageDeclaration
from basstler.review_triage.rules import (
    DEFAULT_RULES,
    ReviewTriageSettings,
    RuleSelection,
    TriageRule,
)

from .samples import RULE_SETTINGS

# %% the settings of a checkout

MODULE_DOCUMENTATION = frozenset({TriageRule.MODULE_DOCUMENTATION})
"""
The one rule there is, as a set.
"""


def test_a_project_selects_rules_in_its_pyproject():
    """
    The rules a project's ``pyproject.toml`` selects are read from its checkout.
    """
    settings = ReviewTriageSettings.from_checkout(RULE_SETTINGS / "selecting")
    assert settings.selection == RuleSelection(select=MODULE_DOCUMENTATION)


def test_a_project_without_settings_selects_no_rule():
    """
    A ``pyproject.toml`` without the settings table chooses no rule.
    """
    settings = ReviewTriageSettings.from_checkout(RULE_SETTINGS / "without-table")
    assert settings.selection == RuleSelection()


def test_a_checkout_without_a_pyproject_selects_no_rule(tmp_path):
    """
    A checkout holding no ``pyproject.toml`` chooses no rule.
    """
    assert ReviewTriageSettings.from_checkout(tmp_path).selection == RuleSelection()


def test_an_unknown_rule_in_the_settings_is_refused():
    """
    A rule that does not exist is an error, never silently ignored.
    """
    with pytest.raises(ValidationError):
        ReviewTriageSettings.from_checkout(RULE_SETTINGS / "unknown-rule")


# %% combining the project's choice with the options


def test_the_default_rules_are_on_when_nothing_chooses():
    """
    With no choice made by the project or the options, the default rules are on.
    """
    assert RuleSelection().applied_to(RuleSelection()) == DEFAULT_RULES


def test_a_project_ignores_a_default_rule():
    """
    A project ignoring a default rule turns it off.
    """
    project = RuleSelection(ignore=DEFAULT_RULES)
    assert RuleSelection().applied_to(project) == frozenset()


def test_an_option_selects_a_rule_the_project_does_not():
    """
    Selecting a rule on the command line enables it.
    """
    options = RuleSelection(select=MODULE_DOCUMENTATION)
    assert options.applied_to(RuleSelection()) == MODULE_DOCUMENTATION


def test_an_option_ignores_a_rule_the_project_selects():
    """
    Ignoring a rule on the command line disables it, outranking the project.
    """
    project = RuleSelection(select=MODULE_DOCUMENTATION)
    options = RuleSelection(ignore=MODULE_DOCUMENTATION)
    assert options.applied_to(project) == frozenset()


def test_a_rule_the_project_both_selects_and_ignores_is_off():
    """
    A project's own ignore outranks its select.
    """
    project = RuleSelection(select=MODULE_DOCUMENTATION, ignore=MODULE_DOCUMENTATION)
    assert RuleSelection().applied_to(project) == frozenset()


# %% the options


def test_the_options_choose_the_rules_of_a_publication():
    """
    The selected and ignored rules of the command line reach the publication.
    """
    publication = TriagePublication.from_arguments(
        7,
        None,
        TriageDeclaration(),
        None,
        None,
        (TriageRule.MODULE_DOCUMENTATION,),
        (),
    )
    assert publication.rule_options == RuleSelection(select=MODULE_DOCUMENTATION)
