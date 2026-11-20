from __future__ import annotations

from ..constants.paths import DATASET
from ..scratch import Scratch


def test_a_scratch_reads_the_dataset():
    assert (Scratch.failure, DATASET) == ("failed", "dataset")
