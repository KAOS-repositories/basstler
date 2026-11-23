"""
Tests for the progress bars of long steps.
"""

from __future__ import annotations

import io
import logging

import pytest

from basstler import progress
from basstler.progress import BarSafeStreamHandler, ProgressStep, ProgressUnit
from basstler.standard_streams import StandardStreamHandler

LOGGED_OUTPUT = "some output"
"""
A command's output, logged at information level while a bar is open.
"""

# %% where a bar is drawn


def test_no_bar_is_drawn_when_standard_error_is_no_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error_stream = io.StringIO()
    monkeypatch.setattr("sys.stderr", error_stream)

    with ProgressStep.JUDGING_FILES.bar(2, ProgressUnit.FILE) as progress:
        progress.update(2)

    assert error_stream.getvalue() == ""


# %% records logged while a bar is drawn


def package_handler_types() -> list[type[logging.Handler]]:
    """
    :return: The type of each handler of the package logger writing to the standard
        streams, in order.
    """
    return [
        type(handler)
        for handler in StandardStreamHandler.package_logger().handlers
        if isinstance(handler, StandardStreamHandler)
    ]


def test_records_are_written_above_an_open_bar_and_as_before_once_it_closes():
    """
    While a bar is open the package writes its records clearing and redrawing the bar,
    and once it closes through its own handler again.
    """
    StandardStreamHandler.logger_for(progress.__name__)

    with ProgressStep.JUDGING_FILES.bar(1, ProgressUnit.FILE):
        while_open = package_handler_types()

    assert (while_open, package_handler_types()) == (
        [BarSafeStreamHandler],
        [StandardStreamHandler],
    )


def test_a_record_logged_while_a_bar_is_open_is_printed_bare(capsys):
    """
    A command's output written above a bar is still its bare message on standard output.
    """
    logger = StandardStreamHandler.logger_for(progress.__name__)

    with ProgressStep.JUDGING_FILES.bar(1, ProgressUnit.FILE):
        logger.info(LOGGED_OUTPUT)

    assert capsys.readouterr().out == f"{LOGGED_OUTPUT}\n"
