"""
Tests that every location the package names is shipped by an installed distribution.
"""

from __future__ import annotations

from itertools import chain

import pytest

from basstler.code_rules.locations import CodeRulesPackageLocation
from basstler.github.locations import GitHubPackageLocation
from basstler.locations import (
    PackageLocation,
    PathEnumeration,
    PluginFile,
    PluginLocation,
)
from basstler.plan.locations import PlanPackageLocation, PlanPluginLocation
from basstler.plan_site.locations import SitePluginLocation
from basstler.setup.locations import SetupPackageLocation, SetupPluginLocation

# %% the package's own files


@pytest.mark.parametrize(
    "location",
    list(
        chain(
            PackageLocation,
            GitHubPackageLocation,
            CodeRulesPackageLocation,
            SetupPackageLocation,
            PlanPackageLocation,
        )
    ),
    ids=lambda member: member._name_,
)
def test_every_shipped_location_exists(location: PathEnumeration):
    """
    A misspelled location would only fail at the first read of it.

    The board is left out, as scratch state a maintenance pass writes.
    """
    assert location.value.exists()


# %% the plugin's scripts


@pytest.mark.parametrize(
    "location",
    list(chain(SetupPluginLocation, PlanPluginLocation, SitePluginLocation)),
    ids=lambda member: member._name_,
)
def test_a_distribution_s_plugin_script_is_one_of_the_plugin_s_hooks(
    location: PluginFile,
):
    """
    The scripts a distribution names for itself sit in the plugin's hooks directory, as
    those of :class:`~basstler.locations.PluginLocation` do.
    """
    assert location.parent == PluginLocation.HOOKS.value
