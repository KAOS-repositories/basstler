"""
The package indexes a release is published to.
"""

from __future__ import annotations

from enum import StrEnum

# %% indexes


class PackageIndex(StrEnum):
    """
    A package index; each value starts the names of the GitHub environments its trusted
    publishers name.
    """

    TESTPYPI = "testpypi"
    PYPI = "pypi"

    @property
    def upload_url(self) -> str | None:
        """
        Where the index takes uploads, unset where the publish action's default, PyPI
        itself, is the address.
        """
        return {
            PackageIndex.TESTPYPI: "https://test.pypi.org/legacy/",
            PackageIndex.PYPI: None,
        }[self]

    def publishing_environment(self, distribution_name: str) -> str:
        """
        :param distribution_name: The distribution published, or an expression giving it.
        :return: The GitHub environment the distribution is published to the index from.
        """
        return f"{self}-{distribution_name}"
