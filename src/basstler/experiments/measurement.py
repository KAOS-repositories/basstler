"""
Repeated measurements of one quantity, summarised as their mean and spread.
"""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass
from enum import StrEnum
from types import TracebackType

# %% units


class Unit(StrEnum):
    """
    The unit a measured quantity is expressed in, written after its value.
    """

    SECONDS = "s"
    """
    Wall-clock time.
    """

    MEGABYTES = "MB"
    """
    Disk space, in millions of bytes.
    """

    COUNT = ""
    """
    A number of things, written without a unit.
    """


BYTES_PER_MEGABYTE = 1_000_000
"""
The bytes in one :attr:`Unit.MEGABYTES`.
"""

# %% one measured quantity


@dataclass(frozen=True)
class Measurement:
    """
    The mean and standard deviation of repeated measurements of one quantity.
    """

    mean: float
    """
    The mean of the measurements.
    """

    standard_deviation: float
    """
    Their sample standard deviation, zero for a single measurement.
    """

    unit: Unit
    """
    What both are expressed in.
    """

    repetitions: int
    """
    How many measurements were taken.
    """

    @classmethod
    def from_samples(cls, samples: list[float], unit: Unit) -> Measurement:
        """
        :param samples: At least one measurement.
        :param unit: What they are expressed in.
        :return: Their summary.
        """
        spread = statistics.stdev(samples) if len(samples) > 1 else 0.0
        return cls(statistics.mean(samples), spread, unit, len(samples))

    def __str__(self) -> str:
        """
        :return: The mean, the deviation only when there is one, and the unit.
        """
        unit = f" {self.unit}" if self.unit else ""
        if self.repetitions == 1:
            return f"{self.mean:.1f}{unit}"
        return f"{self.mean:.1f} ± {self.standard_deviation:.1f}{unit}"


# %% timing


@dataclass
class Stopwatch:
    """
    Measures the wall-clock time of the block it is entered for.
    """

    started: float = 0.0
    """
    The performance counter when the block was entered.
    """

    seconds: float = 0.0
    """
    How long the block took, set once it is left.
    """

    def __enter__(self) -> Stopwatch:
        """
        :return: This stopwatch, started.
        """
        self.started = time.perf_counter()
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """
        Stop the stopwatch, letting any exception through.
        """
        self.seconds = time.perf_counter() - self.started
