"""
The part of the suite one of several parallel runs takes, so a slow runner can run the
suite as several jobs at once.
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
