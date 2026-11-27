"""
Fixtures shared by the plan service's tests.
"""

from __future__ import annotations

import pytest

from basstler.environment import HubInstanceVariable
from basstler.hub_server.configuration import InstanceConfiguration

# %% an instance's configuration


@pytest.fixture
def configuration() -> InstanceConfiguration:
    """
    The configuration of an instance acting as a made-up App.
    """
    return InstanceConfiguration(
        app_id=1234,
        private_key="-----BEGIN RSA PRIVATE KEY-----\nnot a key\n-----END RSA PRIVATE KEY-----",
        webhook_secret="the webhook secret",
    )


@pytest.fixture
def configured_environment(
    configuration: InstanceConfiguration, monkeypatch: pytest.MonkeyPatch
) -> InstanceConfiguration:
    """
    An environment setting every instance variable to :func:`configuration`'s values,
    with no file variable set.
    """
    values = {
        HubInstanceVariable.APP_ID: str(configuration.app_id),
        HubInstanceVariable.PRIVATE_KEY: configuration.private_key,
        HubInstanceVariable.WEBHOOK_SECRET: configuration.webhook_secret,
    }
    for variable, value in values.items():
        monkeypatch.setenv(variable, value)
        monkeypatch.delenv(variable.file_variable, raising=False)
    return configuration
