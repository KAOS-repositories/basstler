"""
Tests for :mod:`basstler.playbook.setup_steps`.
"""

from __future__ import annotations

from pathlib import Path

from basstler.playbook.playbook import Playbook
from basstler.playbook.setup_steps import RepositoryCheckout, SetupChecklist

from .components import LabelledComponent, StepsNamingTheCheckout, TitledStep

CHECKOUT = RepositoryCheckout(Path("/projects/clone"), {})
"""
The checkout every checklist below is worked out for.
"""


def test_the_checklist_lists_every_contributed_step_in_playbook_order():
    """
    Every setup steps component adds its steps, in playbook order.
    """
    playbook = Playbook(
        (
            StepsNamingTheCheckout("first for"),
            LabelledComponent("not a setup step"),
            StepsNamingTheCheckout("then for"),
        )
    )

    assert SetupChecklist.from_checkout(playbook, CHECKOUT) == SetupChecklist(
        (TitledStep("first for clone"), TitledStep("then for clone"))
    )


def test_the_checklist_numbers_each_step_under_its_heading():
    """
    The printed checklist numbers the steps from one under its heading.
    """
    first, second = TitledStep("first"), TitledStep("second")

    assert SetupChecklist((first, second)).render() == "\n\n".join(
        [SetupChecklist.heading, first.render(1), second.render(2)]
    )
