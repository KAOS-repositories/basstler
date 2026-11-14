"""
Fixtures of a headless browser the plan site's scripts are tested in.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, sync_playwright

# %% the browser


@pytest.fixture(scope="session")
def browser() -> Iterator[Browser]:
    """
    :return: A headless Chromium, shared by every test of the session.
    """
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture
def browser_page(browser: Browser) -> Iterator[Page]:
    """
    :param browser: The session's headless Chromium.
    :return: A fresh page in it, closed after the test.
    """
    page = browser.new_page()
    yield page
    page.close()
