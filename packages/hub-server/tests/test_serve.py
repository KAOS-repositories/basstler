"""
Tests for the ``serve`` command of :mod:`basstler.hub_server`: where an instance
listens.
"""

from __future__ import annotations

from typing import Any

import pytest
import uvicorn

from basstler.environment import ContainerHostVariable
from basstler.hub_server.__main__ import DEFAULT_PORT, serve
from basstler.hub_server.configuration import InstanceConfiguration

# %% the address served


@pytest.fixture
def served(
    configured_environment: InstanceConfiguration, monkeypatch: pytest.MonkeyPatch
) -> dict[str, Any]:
    """
    The keyword arguments :func:`uvicorn.run` is called with, instead of serving.
    """
    called: dict[str, Any] = {}
    monkeypatch.setattr(
        uvicorn, "run", lambda application, **arguments: called.update(arguments)
    )
    return called


def test_an_instance_listens_on_the_port_its_host_names(
    served: dict[str, Any], monkeypatch: pytest.MonkeyPatch
):
    """
    A container host names the port it routes requests to.
    """
    monkeypatch.setenv(ContainerHostVariable.PORT, "9000")

    serve()

    assert served["port"] == 9000


def test_an_instance_whose_host_names_no_port_listens_on_the_default(
    served: dict[str, Any], monkeypatch: pytest.MonkeyPatch
):
    """
    ``docker run`` names none, so the instance listens where its documentation says.
    """
    monkeypatch.delenv(ContainerHostVariable.PORT, raising=False)

    serve()

    assert served["port"] == DEFAULT_PORT
