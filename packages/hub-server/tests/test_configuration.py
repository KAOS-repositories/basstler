"""
Tests for :mod:`basstler.hub_server.configuration`: reading an instance's settings from
its environment.
"""

from __future__ import annotations

import pytest

from basstler.environment import HubInstanceVariable
from basstler.hub_server.configuration import InstanceConfiguration
from basstler.hub_server.exceptions import MissingInstanceSetting

# %% reading the environment


def test_the_configuration_is_read_from_the_environment(
    configured_environment: InstanceConfiguration,
):
    """
    Every setting the environment gives is the configuration's.
    """
    assert InstanceConfiguration.from_environment() == configured_environment


def test_a_setting_the_environment_lacks_stops_the_instance(
    configured_environment: InstanceConfiguration, monkeypatch: pytest.MonkeyPatch
):
    """
    An instance missing a setting refuses to start, naming the setting it lacks.
    """
    monkeypatch.delenv(HubInstanceVariable.WEBHOOK_SECRET)

    with pytest.raises(MissingInstanceSetting) as raised:
        InstanceConfiguration.from_environment()

    assert raised.value.setting is HubInstanceVariable.WEBHOOK_SECRET
