from __future__ import annotations

from basstler_testing.constants.paths import DATASET
from basstler_testing.scratch import Scratch


def test_a_scratch_reads_the_dataset():
    assert (Scratch.failure, DATASET) == ("failed", "dataset")
