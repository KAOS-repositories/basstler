"""
Tests for the progress bars of long steps.
"""

from __future__ import annotations

import io

import pytest

from basstler.progress import ProgressStep, ProgressUnit

# %% where a bar is drawn


def test_no_bar_is_drawn_when_standard_error_is_no_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error_stream = io.StringIO()
    monkeypatch.setattr("sys.stderr", error_stream)

    with ProgressStep.JUDGING_FILES.bar(2, ProgressUnit.FILE) as progress:
        progress.update(2)

    assert error_stream.getvalue() == ""
