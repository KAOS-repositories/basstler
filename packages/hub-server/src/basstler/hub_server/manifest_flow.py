"""
GitHub's manifest flow, as seen from the machine that registers the App: a page that
submits the manifest and the redirect that brings the code back.
"""

from __future__ import annotations

import json
import secrets
import time
import webbrowser
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

from basstler.class_property import classproperty
from basstler.hub_server.app_manifest import AppManifest
from basstler.hub_server.exceptions import RegistrationFailure, RegistrationRefused
from basstler.locations import HubServerTemplate
from basstler.render_common import TemplatePage

LOOPBACK_ADDRESS = "127.0.0.1"
"""
The address the flow listens on: this machine alone.
"""

ANY_FREE_PORT = 0
"""
The port number that asks the operating system for a port nobody uses.
"""

# %% what the flow serves


class ManifestFlowPath(StrEnum):
    """
    The paths the flow answers.
    """

    PAGE = "/"
    """
    The page that submits the manifest.
    """

    REDIRECT = "/redirect"
    """
    Where GitHub sends the browser once the App is registered.
    """


class RedirectParameter(StrEnum):
    """
    The query parameters of GitHub's redirect.
    """

    CODE = "code"
    """
    The code that is converted into the App's credentials.
    """

    STATE = "state"
    """
    The state the manifest was submitted with, returned unchanged.
    """


@dataclass(frozen=True)
class ManifestPage(TemplatePage):
    """
    The page that submits a manifest to the registration page as soon as it opens.
    """

    action: str
    """
    The registration page's address, with the state the redirect must return.
    """

    manifest: str
    """
    The manifest, as JSON text.
    """

    @classproperty
    def template(cls) -> str:
        return HubServerTemplate.APP_MANIFEST_PAGE.name

    def render(self) -> str:
        """
        :return: The page's HTML.
        """
        return self.render_template(action=self.action, manifest=self.manifest)


# %% the server


class ManifestFlowServer(HTTPServer):
    """
    A one-visitor server holding what the flow serves and what it received.
    """

    page: str = ""
    """
    The HTML of :attr:`ManifestFlowPath.PAGE`.
    """

    state: str = ""
    """
    The state a redirect has to carry to be accepted.
    """

    code: str | None = None
    """
    The code of the accepted redirect, ``None`` until one arrives.
    """


class ManifestFlowHandler(BaseHTTPRequestHandler):
    """
    Answers the browser: the page that submits the manifest and GitHub's redirect.
    """

    server: ManifestFlowServer

    def do_GET(self) -> None:
        """
        Answer a visit to the page or the redirect, and refuse any other path.
        """
        address = urlsplit(self.path)
        match address.path:
            case ManifestFlowPath.PAGE:
                self.respond(HTTPStatus.OK, self.server.page)
            case ManifestFlowPath.REDIRECT:
                self.accept_redirect(parse_qs(address.query))
            case _:
                self.respond(HTTPStatus.NOT_FOUND, "")

    def accept_redirect(self, parameters: Mapping[str, list[str]]) -> None:
        """
        Keep the redirect's code when its state is the flow's; refuse it otherwise.

        :param parameters: The redirect's query parameters.
        """
        (state,) = parameters.get(RedirectParameter.STATE, [None])
        (code,) = parameters.get(RedirectParameter.CODE, [None])
        if code is None or state != self.server.state:
            self.respond(HTTPStatus.BAD_REQUEST, "")
            return
        self.server.code = code
        self.respond(HTTPStatus.OK, "The App is registered. You can close this tab.")

    def respond(self, status: HTTPStatus, text: str) -> None:
        """
        :param status: The response's status.
        :param text: The response's HTML body.
        """
        body = text.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, message_format: str, *arguments: Any) -> None:
        """
        Write nothing: the command reports what happened itself.
        """


# %% the flow


@dataclass(frozen=True)
class ManifestFlow:
    """
    Submits an App's manifest to GitHub from the user's browser and receives the code
    GitHub redirects back with.
    """

    name: str
    """
    The App's name.
    """

    homepage_url: str
    """
    The App's home page.
    """

    webhook_url: str
    """
    Where GitHub delivers the App's events.
    """

    registration_page: str
    """
    The GitHub page the manifest is submitted to.
    """

    open_browser: Callable[[str], object] = webbrowser.open
    """
    Opens an address in the user's browser.
    """

    timeout: timedelta = timedelta(minutes=5)
    """
    How long the flow waits for the redirect.
    """

    def run(self) -> str:
        """
        Serve the page on this machine, open it in the browser and wait for GitHub's
        redirect.

        :return: The code the redirect carries.
        :raises RegistrationRefused: If no redirect with the flow's state arrives in time.
        """
        with ManifestFlowServer(
            (LOOPBACK_ADDRESS, ANY_FREE_PORT), ManifestFlowHandler
        ) as server:
            origin = f"http://{LOOPBACK_ADDRESS}:{server.server_port}"
            server.state = secrets.token_urlsafe()
            manifest = AppManifest.from_committed(
                name=self.name,
                homepage_url=self.homepage_url,
                webhook_url=self.webhook_url,
                redirect_url=f"{origin}{ManifestFlowPath.REDIRECT}",
            )
            server.page = ManifestPage(
                action=f"{self.registration_page}?{urlencode({RedirectParameter.STATE: server.state})}",
                manifest=json.dumps(manifest.to_json()),
            ).render()
            self.open_browser(f"{origin}{ManifestFlowPath.PAGE}")
            deadline = time.monotonic() + self.timeout.total_seconds()
            while server.code is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RegistrationRefused(RegistrationFailure.TIMED_OUT)
                server.timeout = remaining
                server.handle_request()
            return server.code
