"""
Tests for basstler.plan.decision: the options that answer an owner's decision.
"""

from __future__ import annotations

import pytest

from basstler.plan.decision import Decision, DecisionOption, ExperimentVerdict
from basstler.plan.dependencies import PlanDirectory
from basstler.plan.exceptions import PlanValidationError, UnknownDecision
from basstler.plan.model import ManifestKey
from basstler.plan.structure import Item
from basstler.plan.validation import PlanValidator

from basstler_testing.constants.paths import DatasetLocation
from basstler_testing.manifest_builders import manifest_item, minimal_plan

# %% the options


class TestAnExperimentVerdict:
    """
    An experiment's verdict is answered by accepting, iterating or dropping it.
    """

    @pytest.fixture
    def options(self) -> tuple[DecisionOption, ...]:
        """
        :return: The options the experiment verdict offers.
        """
        return Decision.EXPERIMENT_VERDICT.options

    def test_every_verdict_is_offered_once(self, options: tuple[DecisionOption, ...]):
        """
        The options carry each verdict the skill understands, once each.
        """
        assert sorted(option.argument for option in options) == sorted(
            ExperimentVerdict
        )

    def test_only_iterating_asks_for_a_request(
        self, options: tuple[DecisionOption, ...]
    ):
        """
        Accepting and dropping need no words from the owner; iterating needs them.
        """
        assert {option.argument for option in options if option.asks_for_request} == {
            ExperimentVerdict.ITERATE
        }

    def test_the_command_names_the_item_and_the_verdict(
        self, options: tuple[DecisionOption, ...]
    ):
        """
        An option's command is its skill, the item's reference and the verdict.
        """
        (drop,) = [o for o in options if o.argument == ExperimentVerdict.DROP]
        assert drop.invocation("a-plan", "an-item") == (
            f"{drop.skill_command_name} a-plan/an-item {ExperimentVerdict.DROP}"
        )


# %% declaring a decision


class TestDeclaringADecision:
    """
    A manifest says what an owner's item asks its owner to decide.
    """

    def test_an_item_asks_no_decision_unless_it_says_so(self):
        """
        An entry naming no decision asks none.
        """
        assert Item.from_mapping(manifest_item("a")).decision is None

    def test_an_item_carries_its_decision(self):
        """
        The manifest's decision is read onto the item.
        """
        plan = PlanDirectory(DatasetLocation.DECISION_PLANS).plan("review-experiment")
        (item,) = plan.items
        assert item.decision is Decision.EXPERIMENT_VERDICT

    def test_an_unknown_decision_is_refused(self):
        """
        A decision that is no member of :class:`Decision` is a validation problem.
        """
        items = [manifest_item("a", **{ManifestKey.DECISION.key: "coin-toss"})]
        with pytest.raises(PlanValidationError) as error:
            PlanValidator(minimal_plan(items=items)).validate()
        assert [type(problem) for problem in error.value.problems] == [UnknownDecision]
