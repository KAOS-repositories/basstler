"""
Tests for :mod:`basstler.plan_site.site_repository`: the token form it pre-fills.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

from basstler.github.repository import NewTokenPage, Repository
from basstler.github.token_form import (
    PermissionLevel,
    RepositoryPermission,
    TokenFormParameter,
)
from basstler.plan_site.site_repository import SiteRepository

SITE = SiteRepository(Repository("an-owner", "plans"))
"""
The site repository the token starts the build in.
"""

# %% the pre-filled token form


def test_the_token_form_asks_for_actions_write_under_the_site_owner_only():
    address = urlsplit(SITE.token_form_url())

    fields = parse_qs(address.query)

    assert address._replace(query="").geturl() == NewTokenPage.FINE_GRAINED.url
    assert fields[TokenFormParameter.RESOURCE_OWNER] == [SITE.repository.owner]
    assert fields[RepositoryPermission.ACTIONS] == [PermissionLevel.WRITE]
    assert set(fields) == {*TokenFormParameter, RepositoryPermission.ACTIONS}
