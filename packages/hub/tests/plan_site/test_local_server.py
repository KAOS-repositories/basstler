"""
Tests for serving the local plan site on the loopback address.
"""

from __future__ import annotations

import http.client
import threading
from collections.abc import Iterator
from http import HTTPStatus
from pathlib import Path

import pytest

from basstler.plan_site.local_server import LocalSiteServer
from basstler.plan_site.local_site import LocalSite

from .test_local_site import NumberedBuild, SettableClock

# %% the server


@pytest.fixture
def numbered_build() -> NumberedBuild:
    return NumberedBuild()


@pytest.fixture
def server(numbered_build: NumberedBuild, tmp_path: Path) -> Iterator[LocalSiteServer]:
    """
    :return: A server on a free port, answering on a thread of its own.
    """
    server = LocalSiteServer(
        LocalSite(numbered_build, tmp_path, clock=SettableClock()), port=0
    )
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    yield server
    server.shutdown()
    thread.join()
    server.server_close()


def request(
    server: LocalSiteServer,
    method: str = "GET",
    path: str = "/",
    headers: dict[str, str] | None = None,
) -> tuple[HTTPStatus, str, http.client.HTTPMessage]:
    """
    :return: The status, body and headers of one request to *server*.
    """
    connection = http.client.HTTPConnection(*server.server_address)
    connection.request(method, path, headers=headers or {})
    response = connection.getresponse()
    body = response.read().decode()
    connection.close()
    return HTTPStatus(response.status), body, response.headers


def test_the_server_listens_on_the_loopback_address_only(server: LocalSiteServer):
    assert server.server_address[0] == "127.0.0.1"


def test_a_page_view_serves_the_built_page_with_a_refresh_button(
    server: LocalSiteServer,
):
    status, body, _ = request(server)

    assert status == HTTPStatus.OK
    assert "build 1" in body
    assert '<button type="submit">Refresh</button>' in body


def test_refreshing_rebuilds_and_returns_to_the_page(server: LocalSiteServer):
    request(server)

    status, _, headers = request(server, "POST", "/")

    assert (status, headers["Location"]) == (HTTPStatus.SEE_OTHER, "/")
    assert "build 2" in request(server)[1]


def test_a_refresh_never_redirects_off_the_site(server: LocalSiteServer):
    _, _, headers = request(server, "POST", "//elsewhere.example/")

    assert headers["Location"] == "/elsewhere.example/"


def test_a_failed_build_is_shown_on_the_page(
    server: LocalSiteServer, numbered_build: NumberedBuild
):
    request(server)
    numbered_build.failure = "<GitHub> is unreachable"

    request(server, "POST", "/")
    _, body, _ = request(server)

    assert "build 1" in body
    assert "&lt;GitHub&gt; is unreachable" in body


def test_with_no_build_yet_the_failure_is_served(
    server: LocalSiteServer, numbered_build: NumberedBuild
):
    numbered_build.failure = "no credential"

    status, body, _ = request(server)

    assert status == HTTPStatus.SERVICE_UNAVAILABLE
    assert "no credential" in body


def test_a_request_naming_another_host_is_refused(
    server: LocalSiteServer, numbered_build: NumberedBuild
):
    status, _, _ = request(server, headers={"Host": "elsewhere.example"})

    assert (status, numbered_build.runs) == (HTTPStatus.MISDIRECTED_REQUEST, 0)


def test_a_refresh_from_another_origin_is_refused(
    server: LocalSiteServer, numbered_build: NumberedBuild
):
    status, _, _ = request(
        server, "POST", "/", headers={"Origin": "http://elsewhere.example"}
    )

    assert (status, numbered_build.runs) == (HTTPStatus.FORBIDDEN, 0)


def test_a_missing_page_is_not_found_and_no_directory_is_listed(
    server: LocalSiteServer,
):
    request(server)

    assert request(server, path="/missing/")[0] == HTTPStatus.NOT_FOUND
