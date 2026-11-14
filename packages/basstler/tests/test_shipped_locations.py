"""
Tests that every location the package names is shipped by an installed distribution.
"""

from __future__ import annotations

import pytest

from basstler.locations import PackageLocation

# %% the package's own files


@pytest.mark.parametrize(
    "location",
    list(PackageLocation),
    ids=lambda member: member._name_,
)
def test_every_shipped_location_exists(location: PackageLocation):
    """
    A misspelled location would only fail at the first read of it.

    The board is left out, as scratch state a maintenance pass writes.
    """
    assert location.value.exists()
