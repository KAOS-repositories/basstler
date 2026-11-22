"""
The page that submits the manifest to GitHub and the redirect that brings the code back.
"""

from __future__ import annotations

from datetime import timedelta
from http import HTTPStatus
from urllib.parse import urlsplit

import pytest

from basstler.hub_server.app_manifest import AppManifest
from basstler.hub_server.exceptions import RegistrationFailure, RegistrationRefused
from basstler.hub_server.manifest_flow import ManifestFlow
from .manifest_browser import RedirectedBrowser

REGISTRATION_PAGE = "https://github.example.org/settings/apps/new"
"""
Where the flow under test asks the manifest to be registered.
"""


def flow_with(
    browser: RedirectedBrowser, timeout: timedelta | None = None
) -> ManifestFlow:
    """
    :return: A flow opening its page in *browser*.
    """
    return ManifestFlow(
        name="example-basstlerhub",
        homepage_url="https://hub.example.org",
        webhook_url="https://hub.example.org/webhook",
        registration_page=REGISTRATION_PAGE,
        open_browser=browser,
        **({} if timeout is None else {"timeout": timeout}),
    )


# %% the page


class TestManifestPage:
    """
    What the browser is served and submits.
    """

    def test_the_form_posts_to_the_registration_page(self):
        browser = RedirectedBrowser()
        flow_with(browser).run()
        assert urlsplit(browser.action)._replace(query="").geturl() == REGISTRATION_PAGE

    def test_the_form_carries_the_manifest_redirecting_to_the_flow(self):
        browser = RedirectedBrowser()
        flow_with(browser).run()
        loopback = urlsplit(browser.opened[0])
        assert (
            browser.manifest
            == AppManifest.from_committed(
                name="example-basstlerhub",
                homepage_url="https://hub.example.org",
                webhook_url="https://hub.example.org/webhook",
                redirect_url=f"http://{loopback.netloc}/redirect",
            ).to_json()
        )


# %% the redirect


class TestRedirect:
    """
    The code GitHub redirects the browser back with.
    """

    def test_the_code_in_the_redirect_is_returned(self):
        assert flow_with(RedirectedBrowser(code="the-code")).run() == "the-code"

    def test_a_redirect_with_another_state_is_refused_and_waited_past(self):
        browser = RedirectedBrowser(code="the-code", wrong_state_first=True)
        code = flow_with(browser).run()
        browser.finish()
        assert (code, browser.redirect_statuses) == (
            "the-code",
            [HTTPStatus.BAD_REQUEST, HTTPStatus.OK],
        )

    def test_a_flow_nobody_completes_is_refused(self):
        with pytest.raises(RegistrationRefused) as refusal:
            flow_with(lambda url: None, timeout=timedelta(milliseconds=200)).run()
        assert refusal.value.failure is RegistrationFailure.TIMED_OUT
