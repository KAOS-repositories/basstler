"""
Tests that the plan site's pages render from templates the hub distribution ships.
"""

from __future__ import annotations

import pytest

from basstler.locations import INSTALLED_PACKAGE, ShippedPath, SiteTemplate
from basstler.plan_site.hub_page import HubPage
from basstler.plan_site.plan_page import PlanPage
from basstler.render_common import TemplatePage, create_template_environment

# %% the site's templates


def test_template_environment_finds_the_committed_templates():
    """
    The environment every page renders through finds the plan page's template.
    """
    environment = create_template_environment()
    assert environment.get_template(SiteTemplate.PLAN.name)


@pytest.mark.parametrize("page", [PlanPage, HubPage])
def test_every_page_names_a_template_the_package_ships(
    page: type[TemplatePage],
) -> None:
    """
    Each page's template is a file the installed distributions ship.
    """
    assert INSTALLED_PACKAGE.shipped(ShippedPath.TEMPLATES / page.template).is_file()
