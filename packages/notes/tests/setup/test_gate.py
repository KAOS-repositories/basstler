"""
Tests for :mod:`basstler.setup.gate`'s command line: a skill is named as a session
invokes it.
"""

from __future__ import annotations

import pytest

from basstler.setup.exceptions import UnknownSkillError
from basstler.setup.gate import BasstlerSkill, GateOption, gate_app

# %% naming the skill


@pytest.mark.parametrize("skill", BasstlerSkill.every_skill())
def test_a_skill_is_named_as_a_session_invokes_it(skill: type[BasstlerSkill]):
    """
    The command takes a skill by the name its document runs the gate with.
    """
    _, bound, _ = gate_app.parse_args([GateOption.SKILL, skill.skill_name])

    assert BasstlerSkill.named(bound.arguments["skill"]) is skill


def test_a_name_no_skill_has_is_refused():
    """
    Asking for a skill the gate does not know is a usage error naming it.
    """
    with pytest.raises(UnknownSkillError) as refusal:
        BasstlerSkill.named("no-such-skill")

    assert refusal.value.skill_name == "no-such-skill"
