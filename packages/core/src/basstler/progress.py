"""
Progress bars on the terminal for the steps a command takes long over.

A bar is drawn on standard error and only when that is a terminal, so a command's
output, a pipe or a test sees none of it.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from enum import StrEnum

from tqdm import tqdm

from basstler.standard_streams import StandardStreamHandler

# %% writing records above a bar


class BarSafeStreamHandler(StandardStreamHandler):
    """
    Writes each record as :class:`StandardStreamHandler` does, clearing the progress bars
    drawn at the time and drawing them again below it.
    """

    def emit(self, record: logging.LogRecord) -> None:
        """
        :meth:`StandardStreamHandler.emit`, through :meth:`tqdm.write`.
        """
        tqdm.write(self.format(record), file=self.stream_for(record))

    @classmethod
    @contextmanager
    def installed(cls) -> Iterator[None]:
        """
        Write the package's records through this handler instead of each
        :class:`StandardStreamHandler` it has, until the context ends.
        """
        package_logger = StandardStreamHandler.package_logger()
        replaced = [
            handler
            for handler in package_logger.handlers
            if type(handler) is StandardStreamHandler
        ]
        for handler in replaced:
            package_logger.removeHandler(handler)
            package_logger.addHandler(cls(handler.message_format))
        try:
            yield
        finally:
            for handler in list(package_logger.handlers):
                if isinstance(handler, cls):
                    package_logger.removeHandler(handler)
            for handler in replaced:
                package_logger.addHandler(handler)


# %% progress bars


class ProgressUnit(StrEnum):
    """
    What a progress bar counts.
    """

    FILE = "file"
    """
    A file of a pull request.
    """

    DETECTION = "detection"
    """
    One way of finding a pull request's renames or moves.
    """


class ProgressStep(StrEnum):
    """
    A step a progress bar is drawn for, by the description it shows.
    """

    FINDING_RENAMES_AND_MOVES = "Finding renames and moves"
    """
    Collecting a pull request's renames and moved definitions, one detection at a time.
    """

    JUDGING_FILES = "Judging files"
    """
    Deciding of each file of a pull request whether a reviewer has to read it.
    """

    MARKING_VIEWED = "Marking files viewed"
    """
    Marking a pull request's mechanical files viewed on GitHub.
    """

    @contextmanager
    def bar(self, total: int, unit: ProgressUnit) -> Iterator[tqdm[None]]:
        """
        :param total: How many units the step takes.
        :param unit: What it counts.
        :return: A bar for the step, advanced with :meth:`tqdm.update` and cleared
            once closed, the package's records written above it meanwhile; drawing
            nothing when standard error is no terminal.
        """
        with (
            tqdm(
                total=total,
                desc=self.value,
                unit=f" {unit.value}",
                file=sys.stderr,
                disable=None,
                leave=False,
                dynamic_ncols=True,
            ) as progress,
            BarSafeStreamHandler.installed(),
        ):
            yield progress
