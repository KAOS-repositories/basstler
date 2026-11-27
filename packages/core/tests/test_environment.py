"""
Tests for :mod:`basstler.environment`: reading the environment variables this package
reads.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from basstler.environment import EnvironmentFlag, HubInstanceVariable
from basstler.locations import ClaudeCodeVariable
from basstler.text_file import TextFile

# %% reading a flag


def test_a_flag_set_to_true_reads_as_true(monkeypatch: pytest.MonkeyPatch):
    """
    A variable set to :attr:`EnvironmentFlag.TRUE` is true.
    """
    monkeypatch.setenv(ClaudeCodeVariable.REMOTE, EnvironmentFlag.TRUE)

    assert ClaudeCodeVariable.REMOTE.is_true()


def test_an_unset_flag_reads_as_false(monkeypatch: pytest.MonkeyPatch):
    """
    A variable that is not set is not true.
    """
    monkeypatch.delenv(ClaudeCodeVariable.REMOTE, raising=False)

    assert not ClaudeCodeVariable.REMOTE.is_true()


# %% reading an instance setting from its variable or from a mounted file

SETTING_VALUE = "a webhook secret"
"""
The value every instance-setting test gives the setting.
"""


@pytest.fixture
def unset_setting(monkeypatch: pytest.MonkeyPatch) -> HubInstanceVariable:
    """
    The webhook secret, with neither its variable nor its file variable set.
    """
    setting = HubInstanceVariable.WEBHOOK_SECRET
    monkeypatch.delenv(setting, raising=False)
    monkeypatch.delenv(setting.file_variable, raising=False)
    return setting


def test_a_setting_is_read_from_its_variable(
    unset_setting: HubInstanceVariable, monkeypatch: pytest.MonkeyPatch
):
    """
    A value set in the variable itself is the setting.
    """
    monkeypatch.setenv(unset_setting, SETTING_VALUE)

    assert unset_setting.read_value_or_file() == SETTING_VALUE


def test_a_setting_is_read_from_the_file_its_file_variable_names(
    unset_setting: HubInstanceVariable,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    """
    A container host mounts a secret as a file, so the variable ending in ``_FILE``
    names a file holding the setting; the newline that ends the file is not part of it.
    """
    secret_file = tmp_path / "webhook-secret"
    TextFile(secret_file).write(f"{SETTING_VALUE}\n")
    monkeypatch.setenv(unset_setting.file_variable, str(secret_file))

    assert unset_setting.read_value_or_file() == SETTING_VALUE


def test_a_setting_given_neither_way_is_absent(unset_setting: HubInstanceVariable):
    """
    With neither variable set there is no value to read.
    """
    assert unset_setting.read_value_or_file() is None
