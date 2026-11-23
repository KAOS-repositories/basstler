from __future__ import annotations

from .command_failures import FAILURE
from basstler_testing.scratch import Scratch


def test_a_scratch_fails():
    assert Scratch.failure == FAILURE
