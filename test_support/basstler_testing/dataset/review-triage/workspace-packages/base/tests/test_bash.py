from __future__ import annotations

from .command_failures import FAILURE
from .scratch import Scratch


def test_a_scratch_fails():
    assert Scratch.failure == FAILURE
