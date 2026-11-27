"""
A browser, as the registration flow sees it: it opens the page the flow serves, submits
the manifest to GitHub, and follows GitHub's redirect back.
"""

from __future__ import annotations

import html
import json
import threading
from dataclasses import dataclass, field
from http import HTTPStatus
from http.client import HTTPConnection
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, urlsplit

# %% reading the page the flow serves


class ManifestFormReader(HTMLParser):
    """
    Reads the form that submits the manifest: where it posts and what it carries.
    """

    action: str | None = None
    """
    The address the form posts to.
    """

    manifest_text: str | None = None
    """
    The value of the field carrying the manifest.
    """

    def handle_starttag(
        self, tag: str, attributes: list[tuple[str, str | None]]
    ) -> None:
        fields = dict(attributes)
        if tag == "form":
            self.action = fields["action"]
        if tag == "input":
            self.manifest_text = html.unescape(fields["value"] or "")


# %% the browser


@dataclass
class RedirectedBrowser:
    """
    Opens the flow's page and, as GitHub would, sends the browser back to the flow with
    a code and the state the form carried.
    """

    code: str = "example-code"
    """
    The code GitHub redirects with.
    """

    wrong_state_first: bool = False
    """
    Whether the browser first arrives with a state that is not the one the flow made.
    """

    action: str | None = None
    """
    Where the form posted the manifest to, once the page was read.
    """

    manifest: dict[str, Any] = field(default_factory=dict)
    """
    The manifest the form carried, once the page was read.
    """

    redirect_statuses: list[HTTPStatus] = field(default_factory=list)
    """
    The status the flow answered each redirect with, first first.
    """

    opened: list[str] = field(default_factory=list)
    """
    Every address the browser was asked to open.
    """

    visits: list[threading.Thread] = field(default_factory=list)
    """
    The background visit of each address opened.
    """

    def __call__(self, url: str) -> None:
        """
        Open *url* in the background, as a browser does.
        """
        self.opened.append(url)
        self.visits.append(threading.Thread(target=self.follow, args=(url,)))
        self.visits[-1].start()

    def finish(self) -> None:
        """
        Wait until every page the browser opened has been followed to its end.
        """
        for visit in self.visits:
            visit.join()

    def follow(self, url: str) -> None:
        """
        Read the page at *url*, then arrive at the redirect address GitHub would send
        the browser to.
        """
        address = urlsplit(url)
        connection = HTTPConnection(address.netloc)
        connection.request("GET", address.path)
        reader = ManifestFormReader()
        reader.feed(connection.getresponse().read().decode())
        self.action = reader.action
        self.manifest = json.loads(reader.manifest_text)
        state = parse_qs(urlsplit(self.action).query)["state"][0]
        redirect = urlsplit(self.manifest["redirect_url"])
        for sent_state in (["wrong"] if self.wrong_state_first else []) + [state]:
            connection = HTTPConnection(redirect.netloc)
            connection.request(
                "GET", f"{redirect.path}?code={self.code}&state={sent_state}"
            )
            self.redirect_statuses.append(HTTPStatus(connection.getresponse().status))
