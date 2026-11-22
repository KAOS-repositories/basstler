"""
The package indexes a release is published to.
"""

from __future__ import annotations

from enum import StrEnum

# %% indexes


class PackageIndex(StrEnum):
    """
    A package index; each value is the GitHub environment that index's trusted publisher
    names.
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
