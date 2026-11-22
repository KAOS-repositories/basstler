"""
The family of distributions basstler is released as.
"""

from __future__ import annotations

from dataclasses import dataclass

from basstler.build.distribution_family import DistributionFamily

# %% the family


@dataclass(frozen=True)
class BasstlerFamily(DistributionFamily):
    """
    The distributions released together as basstler: ``basstler`` and every
    ``basstler-<part>``.
    """

    family_name: str = "basstler"
    """
    The name every basstler distribution starts with.
    """
