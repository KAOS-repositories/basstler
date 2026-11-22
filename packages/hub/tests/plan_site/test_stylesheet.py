"""
Tests that the site's stylesheet styles every class an item's state renders as.
"""

from __future__ import annotations

import pytest

from basstler.locations import SiteTemplate
from basstler.plan.model import ItemStatus
from basstler.plan.structure import Item
from basstler.text_file import TextFile

# %% the status classes


@pytest.mark.parametrize("status", list(ItemStatus))
def test_the_site_styles_every_status_css_class(status):
    """
    A status value holds spaces, so the class is built from the member's name, and the
    stylesheet has to know that name.
    """
    item = Item(title="A", branch="a", track="track-1", status=status)
    stylesheet = TextFile(SiteTemplate.STYLESHEET).read()
    assert f".item.{item.status_and_drift_css_class} " in stylesheet
