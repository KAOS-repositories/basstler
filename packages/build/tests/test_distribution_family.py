"""
Tests for :mod:`basstler.build.distribution_family`.
"""

from __future__ import annotations

import pytest
from basstler.build.distribution_family import DistributionFamily

# %% membership


@pytest.mark.parametrize(
    ("distribution_name", "included"),
    [
        ("sample", True),
        ("sample-core", True),
        ("Sample_Core", True),
        ("samplish", False),
        ("pyyaml", False),
    ],
)
def test_the_family_is_its_name_and_the_hyphenated_parts(
    distribution_name: str, included: bool
):
    """
    Each name beside whether it belongs to the family.
    """
    assert (
        DistributionFamily("sample").includes_distribution(distribution_name)
        is included
    )
