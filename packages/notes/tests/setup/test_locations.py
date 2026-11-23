"""
Tests for the files of a checkout the setup reads.
"""

from __future__ import annotations

import tomllib

from basstler.locations import PackageLocation
from basstler.setup.locations import SetupPackageLocation

# %% the meta-package's metadata


def test_the_meta_package_metadata_names_the_package_s_own_distribution():
    """
    The metadata a checkout's requirements start from is that of the distribution the
    package is named after.
    """
    metadata = tomllib.loads(
        SetupPackageLocation.META_PACKAGE_METADATA.value.read_text(encoding="utf-8")
    )

    assert metadata["project"]["name"] == PackageLocation.DIRECTORY.value.name
