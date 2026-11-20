"""
Progress bars on the terminal for the steps a command takes long over.

A bar is drawn on standard error and only when that is a terminal, so a command's
output, a pipe or a test sees none of it.
"""

from __future__ import annotations

import sys
from enum import StrEnum

from tqdm import tqdm

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

    def bar(self, total: int, unit: ProgressUnit) -> tqdm[None]:
        """
        :param total: How many units the step takes.
        :param unit: What it counts.
        :return: A bar for the step, advanced with :meth:`tqdm.update` and cleared
            once closed; drawing nothing when standard error is no terminal.
        """
        return tqdm(
            total=total,
            desc=self.value,
            unit=f" {unit.value}",
            file=sys.stderr,
            disable=None,
            leave=False,
            dynamic_ncols=True,
        )
