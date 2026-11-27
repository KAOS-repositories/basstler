"""
The plan service's web application: the routes an instance answers.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from functools import cached_property
from http import HTTPMethod, HTTPStatus

from githubkit.webhooks import verify
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from basstler.hub_server.configuration import InstanceConfiguration
from basstler.standard_streams import StandardStreamHandler

logger = StandardStreamHandler.logger_for(__name__)
"""
This module's logger, which reports each delivery received.
"""

# %% vocabulary


class ServerRoute(StrEnum):
    """
    The paths an instance answers.
    """

    HEALTH = "/health"
    """
    Answers once the instance has started, for a container host's probes.
    """

    WEBHOOKS = "/webhooks"
    """
    Receives the App's webhook deliveries; the App's webhook address ends with it.
    """


class WebhookHeader(StrEnum):
    """
    The headers GitHub sends with a webhook delivery that the instance reads.
    """

    SIGNATURE = "X-Hub-Signature-256"
    """
    The HMAC-SHA256 of the body under the webhook secret, prefixed ``sha256=``.
    """

    EVENT = "X-GitHub-Event"
    """
    The name of the event delivered.
    """

    DELIVERY = "X-GitHub-Delivery"
    """
    The delivery's unique ID.
    """


# %% the server


@dataclass(frozen=True)
class HubServer:
    """
    One instance of the plan service, answering with its App's configuration.
    """

    configuration: InstanceConfiguration
    """
    The settings the instance runs with.
    """

    @cached_property
    def application(self) -> Starlette:
        """
        The ASGI application serving every :class:`ServerRoute`.
        """
        return Starlette(
            routes=[
                Route(ServerRoute.HEALTH, self.report_health, methods=[HTTPMethod.GET]),
                Route(
                    ServerRoute.WEBHOOKS,
                    self.receive_webhook,
                    methods=[HTTPMethod.POST],
                ),
            ]
        )

    async def report_health(self, request: Request) -> Response:
        """
        :return: An empty success, since answering at all is the health reported.
        """
        return Response(status_code=HTTPStatus.OK)

    async def receive_webhook(self, request: Request) -> Response:
        """
        :return: :attr:`HTTPStatus.ACCEPTED` for a delivery signed with the webhook
            secret, :attr:`HTTPStatus.UNAUTHORIZED` for any other request.
        """
        body = await request.body()
        signature = request.headers.get(WebhookHeader.SIGNATURE)
        if signature is None or not verify(
            self.configuration.webhook_secret, body, signature
        ):
            return Response(status_code=HTTPStatus.UNAUTHORIZED)
        logger.info(
            f"Received {request.headers.get(WebhookHeader.EVENT)} delivery "
            f"{request.headers.get(WebhookHeader.DELIVERY)}."
        )
        return Response(status_code=HTTPStatus.ACCEPTED)
