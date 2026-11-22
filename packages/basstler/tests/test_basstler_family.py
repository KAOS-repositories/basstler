"""
Tests for :mod:`basstler.basstler_family`.
"""

from __future__ import annotations

import pytest
from basstler.basstler_family import BasstlerFamily

# %% membership


@pytest.mark.parametrize(
    ("distribution_name", "included"),
    [
        ("basstler", True),
        ("basstler-core", True),
        ("basstlerish", False),
        ("pyyaml", False),
    ],
)
def test_the_family_is_basstler_and_its_hyphenated_parts(
    distribution_name: str, included: bool
):
    """
    Each name beside whether it belongs to the family.
    """
    assert BasstlerFamily().includes_distribution(distribution_name) is included
