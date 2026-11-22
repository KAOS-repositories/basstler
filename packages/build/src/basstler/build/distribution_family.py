"""
A family of distributions, which share a name and are released together.
"""

from __future__ import annotations

from dataclasses import dataclass

from packaging.utils import canonicalize_name

# %% the family


@dataclass(frozen=True)
class DistributionFamily:
    """
    The distributions named for one project: the project's own name, alone or followed by
    a hyphen and a part.
    """

    family_name: str
    """
    The name every distribution of the family starts with.
    """

    def includes_distribution(self, distribution_name: str) -> bool:
        """
        :param distribution_name: The name of a distribution.
        :return: Whether it is the family's own distribution or one of its parts.
        """
        name = canonicalize_name(distribution_name)
        family = canonicalize_name(self.family_name)
        return name == family or name.startswith(f"{family}-")
