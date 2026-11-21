"""
Tests for :mod:`tests.suite_shard`: splitting the suite between parallel runs.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from .constants.environment import InterpreterVariable
from .constants.paths import RepositoryLocation
from .dataset import suite_shard_holdings
from .suite_shard import SuiteShard

TEST_IDENTIFIERS = [
    f"tests/test_module_{number}.py::test_case" for number in range(400)
]
"""
Identifiers of as many tests as a small suite has.
"""

SUITE_SHARD_HOLDINGS_MODULE = suite_shard_holdings.__name__
"""
The module printing which identifiers the second of four shards holds.
"""

# %% splitting


def test_every_test_runs_in_exactly_one_shard():
    shards = [SuiteShard(index=index, count=4) for index in range(4)]

    holders = [
        sum(shard.holds(identifier) for shard in shards)
        for identifier in TEST_IDENTIFIERS
    ]

    assert set(holders) == {1}


def test_the_whole_suite_is_one_shard():
    shard = SuiteShard(index=0, count=1)

    assert all(shard.holds(identifier) for identifier in TEST_IDENTIFIERS)


def test_a_test_falls_in_the_same_shard_in_every_process():
    """
    Every xdist worker of every shard collects the suite again, and they all have to
    agree, though each process hashes strings with a seed of its own.
    """
    shard = SuiteShard(index=1, count=4)
    held_here = [shard.holds(identifier) for identifier in TEST_IDENTIFIERS]

    held_in_another_process = subprocess.run(
        [sys.executable, "-m", SUITE_SHARD_HOLDINGS_MODULE],
        input=json.dumps(TEST_IDENTIFIERS),
        capture_output=True,
        check=True,
        encoding="utf-8",
        cwd=RepositoryLocation.ROOT.value,
        env={**os.environ, InterpreterVariable.HASH_SEED: "1"},
    ).stdout

    assert json.loads(held_in_another_process) == held_here


def test_the_shards_take_shares_of_the_suite_near_an_even_split():
    shards = [SuiteShard(index=index, count=4) for index in range(4)]

    sizes = [
        sum(shard.holds(identifier) for identifier in TEST_IDENTIFIERS)
        for shard in shards
    ]

    even_share = len(TEST_IDENTIFIERS) // len(shards)
    assert all(abs(size - even_share) < even_share // 4 for size in sizes)


# %% shards that do not exist


@pytest.mark.parametrize("index", [-1, 4])
def test_a_shard_outside_the_count_is_refused(index):
    with pytest.raises(pytest.UsageError):
        SuiteShard(index=index, count=4)


def test_no_shards_are_refused():
    with pytest.raises(pytest.UsageError):
        SuiteShard(index=0, count=0)
