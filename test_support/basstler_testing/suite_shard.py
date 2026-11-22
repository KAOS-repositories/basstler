"""
The part of the suite one of several parallel runs takes, so a slow runner can run the
suite as several jobs at once. Loaded as a pytest plugin (``-p``), it adds the options
and leaves out the tests another shard holds.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass
from enum import StrEnum

import pytest

# %% the options choosing a shard


class SuiteShardOption(StrEnum):
    """
    The command line options of :class:`SuiteShard`.
    """

    INDEX = "--shard-index"
    """
    Which shard this run takes, counting from zero.
    """

    COUNT = "--shard-count"
    """
    How many shards the suite is split into.
    """


# %% the shard


@dataclass(frozen=True)
class SuiteShard:
    """
    One of :attr:`count` shards of the suite; every test falls in exactly one.
    """

    index: int
    """
    Which shard this is, counting from zero.
    """

    count: int
    """
    How many shards the suite is split into.
    """

    def __post_init__(self) -> None:
        if not 0 <= self.index < self.count:
            raise pytest.UsageError(
                f"{SuiteShardOption.INDEX} {self.index} is not a shard of "
                f"{SuiteShardOption.COUNT} {self.count}"
            )

    @classmethod
    def from_options(cls, config: pytest.Config) -> SuiteShard:
        """
        :param config: The run's configuration.
        :return: The shard its options choose, the whole suite when they choose none.
        """
        return cls(
            index=config.getoption(SuiteShardOption.INDEX),
            count=config.getoption(SuiteShardOption.COUNT),
        )

    def holds(self, test_identifier: str) -> bool:
        """
        :param test_identifier: A test's node id.
        :return: Whether the test falls in this shard, the same in every process.
        """
        return zlib.crc32(test_identifier.encode("utf-8")) % self.count == self.index


# %% the shard of the suite this run takes


def pytest_addoption(parser: pytest.Parser) -> None:
    """
    Declare the options choosing the :class:`SuiteShard` a run takes.

    :param parser: The run's option parser.
    """
    parser.addoption(
        SuiteShardOption.INDEX,
        type=int,
        default=0,
        help="Run only the shard of the suite with this index, counting from zero.",
    )
    parser.addoption(
        SuiteShardOption.COUNT,
        type=int,
        default=1,
        help="Split the suite into this many shards.",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """
    Leave out every test the run's shard does not hold.

    :param config: The run's configuration.
    :param items: The collected tests, narrowed in place.
    """
    shard = SuiteShard.from_options(config)
    held = [item for item in items if shard.holds(item.nodeid)]
    left_out = [item for item in items if not shard.holds(item.nodeid)]
    if left_out:
        config.hook.pytest_deselected(items=left_out)
        items[:] = held
