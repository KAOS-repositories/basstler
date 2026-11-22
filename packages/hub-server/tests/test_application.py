"""
Tests for :mod:`basstler.hub_server.application`: the routes the plan service answers.
"""

from __future__ import annotations

from http import HTTPStatus
from pathlib import Path

import pytest
from githubkit.webhooks import sign
from starlette.testclient import TestClient

from basstler.hub_server.application import HubServer, ServerRoute, WebhookHeader
from basstler.hub_server.configuration import InstanceConfiguration

PING_DELIVERY = Path(__file__).parent / "dataset" / "ping-delivery.json"
"""
The body of a ping delivery, the first event GitHub sends an App's webhook.
"""

# %% the server


@pytest.fixture
def client(configuration: InstanceConfiguration) -> TestClient:
    """
    A client of a server configured with :func:`configuration`.
    """
    return TestClient(HubServer(configuration).application)


@pytest.fixture
def delivery() -> bytes:
    """
    The body of a ping delivery.
    """
    return PING_DELIVERY.read_bytes()


# %% health


def test_a_running_server_reports_itself_healthy(client: TestClient):
    """
    A container host probes this route to know the instance has started.
    """
    assert client.get(ServerRoute.HEALTH).status_code == HTTPStatus.OK


# %% webhook deliveries


def test_a_delivery_signed_with_the_secret_is_accepted(
    client: TestClient, configuration: InstanceConfiguration, delivery: bytes
):
    """
    A delivery GitHub signed with the App's webhook secret is acknowledged.
    """
    response = client.post(
        ServerRoute.WEBHOOKS,
        content=delivery,
        headers={WebhookHeader.SIGNATURE: sign(configuration.webhook_secret, delivery)},
    )

    assert response.status_code == HTTPStatus.ACCEPTED


def test_a_delivery_signed_with_another_secret_is_refused(
    client: TestClient, delivery: bytes
):
    """
    Anyone can post to the address, so a delivery not signed with the secret is refused.
    """
    response = client.post(
        ServerRoute.WEBHOOKS,
        content=delivery,
        headers={WebhookHeader.SIGNATURE: sign("another secret", delivery)},
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_an_unsigned_delivery_is_refused(client: TestClient, delivery: bytes):
    """
    A delivery without a signature cannot be told from anyone else's request.
    """
    response = client.post(ServerRoute.WEBHOOKS, content=delivery)

    assert response.status_code == HTTPStatus.UNAUTHORIZED
