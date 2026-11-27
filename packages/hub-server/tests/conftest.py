"""
The shared fixtures this distribution's tests use.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from basstler_testing.constants.paths import DatasetLocation

from basstler.hub_server.app_credentials import AppCredentials

# %% the credentials GitHub hands over


@pytest.fixture
def conversion_response() -> dict:
    """
    What GitHub answers when a manifest's code is converted.
    """
    return json.loads(
        DatasetLocation.APP_MANIFEST_CONVERSION.read_text(encoding="utf-8")
    )


@pytest.fixture
def credentials(conversion_response: dict) -> AppCredentials:
    """
    The credentials read out of :func:`conversion_response`.
    """
    return AppCredentials.from_json(conversion_response)


@pytest.fixture
def secret_directory(tmp_path: Path) -> Path:
    """
    An empty directory standing for an instance's secret store.
    """
    return tmp_path / "secrets"
