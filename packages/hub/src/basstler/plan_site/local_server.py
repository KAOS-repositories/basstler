"""
Serving the locally built plan site on the loopback address.
"""

from __future__ import annotations

from http import HTTPStatus
from enum import StrEnum
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import override
from urllib.parse import urlsplit

from basstler.plan_site.__main__ import SiteFile
from basstler.plan_site.local_site import LocalSite
from basstler.plan_site.locations import SiteTemplate
from basstler.render_common import TemplatePage
from basstler.text_file import TextFile

LOOPBACK_ADDRESS = "127.0.0.1"
"""
The only address the site is served on, so no other computer reaches it.
"""


class PageMarkup(StrEnum):
    """
    The markup of a built page the server looks for.
    """

    BODY_END = "</body>"
    """
    Where a page's body ends.
    """


def local_site_url(port: int) -> str:
    """
    :param port: The port the site is served on.
    :return: The address the site is served from.
    """
    return f"http://{LOOPBACK_ADDRESS}:{port}/"


class LocalSiteServer(ThreadingHTTPServer):
    """
    Serves a :class:`LocalSite`, refusing requests naming any other host.
    """

    def __init__(self, site: LocalSite, port: int) -> None:
        """
        :param site: The site to serve.
        :param port: The port to listen on, any free one when 0.
        """
        super().__init__((LOOPBACK_ADDRESS, port), LocalSiteRequestHandler)
        self.site = site

    @property
    def url(self) -> str:
        """
        The address the site is served from.
        """
        return local_site_url(self.server_port)

    @property
    def hosts(self) -> frozenset[str]:
        """
        The ``Host`` headers a request on this computer names the server with.
        """
        return frozenset(
            f"{host}:{self.server_port}" for host in (LOOPBACK_ADDRESS, "localhost")
        )


class LocalSiteRequestHandler(SimpleHTTPRequestHandler):
    """
    Answers a page view with a current build, and a form post by building anew.
    """

    server: LocalSiteServer

    def __init__(self, *arguments: object) -> None:
        super().__init__(*arguments, directory=None)

    @override
    def parse_request(self) -> bool:
        if not super().parse_request():
            return False
        # A page of another site resolving its name to this computer must not read ours.
        if self.headers.get("Host") not in self.server.hosts:
            self.send_error(HTTPStatus.MISDIRECTED_REQUEST)
            return False
        return True

    @override
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    @override
    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        is_page = path.endswith(("/", f"/{SiteFile.PAGE}"))
        if is_page:
            self.server.site.refresh_if_stale()
        if self.server.site.current is None:
            self.send_page(HTTPStatus.SERVICE_UNAVAILABLE, "")
            return
        self.directory = str(self.server.site.current)
        file = Path(self.translate_path(self.path))
        if is_page and path.endswith("/"):
            file /= SiteFile.PAGE
        if is_page and file.is_file():
            self.send_page(HTTPStatus.OK, TextFile(file).read())
            return
        super().do_GET()

    def do_POST(self) -> None:
        """
        Build the site anew, then send the browser back to the page it posted from.
        """
        origin = self.headers.get("Origin")
        if origin is not None and urlsplit(origin).netloc not in self.server.hosts:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        self.server.site.refresh()
        self.send_response(HTTPStatus.SEE_OTHER)
        # One leading slash only: two would send the browser to another host.
        self.send_header("Location", f"/{self.path.lstrip('/')}")
        self.send_header("Content-Length", "0")
        self.end_headers()

    @override
    def list_directory(self, path: str) -> None:
        self.send_error(HTTPStatus.NOT_FOUND)

    def send_page(self, status: HTTPStatus, page: str) -> None:
        """
        :param status: The answer's status.
        :param page: The built page, which the bar is added to the end of.
        """
        site = self.server.site
        bar = TemplatePage.render_named_template(
            SiteTemplate.LOCAL_SITE_BAR.name,
            built_at=(
                site.built_at.astimezone().strftime("%Y-%m-%d %H:%M:%S")
                if site.built_at is not None
                else None
            ),
            failure=site.failure,
        )
        content, closing, rest = page.rpartition(PageMarkup.BODY_END)
        body = f"{content}{bar}{closing}{rest}" if closing else f"{page}{bar}"
        encoded = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)
