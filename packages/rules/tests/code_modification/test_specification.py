"""
Tests for :mod:`basstler.code_modification.specification`: telling places that share
code apart from places that do not.
"""

from __future__ import annotations

import libcst
import pytest

from basstler.code_modification.positions import PositionedModule
from basstler.code_modification.specification import Specification

from basstler_testing.constants.paths import CodeModificationSnippet


@pytest.fixture
def calls() -> dict[str, Specification]:
    """
    :return: Each call of the nested and adjacent calls, as a place, by the name it
        calls.
    """
    module = PositionedModule(
        libcst.parse_module(
            CodeModificationSnippet.NESTED_AND_ADJACENT_CALLS.read_text(
                encoding="utf-8"
            )
        )
    )
    return {
        node.func.value: Specification(location, node)
        for node, location in module.positions.items()
        if isinstance(node, libcst.Call)
    }


def test_a_place_inside_another_overlaps_it(calls):
    """
    A call nested in another's arguments shares code with it, either way round.
    """
    assert calls["abs"].overlaps(calls["round"])
    assert calls["round"].overlaps(calls["abs"])


def test_places_side_by_side_do_not_overlap(calls):
    """
    Two calls joined by an operator share no character.
    """
    assert not calls["abs"].overlaps(calls["len"])
