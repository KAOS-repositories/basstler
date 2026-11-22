"""
The distributions one release builds, read back from the files ``uv build`` wrote.
"""

from __future__ import annotations

import tarfile
import zipfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

# %% vocabulary


class ReleaseFile(StrEnum):
    """
    The files every distribution ships beside its code, named as in the repository root.
    """

    LICENSE = "LICENSE"
    NOTICE = "NOTICE"


class DistributionSuffix(StrEnum):
    """
    The endings of the files a build writes.
    """

    WHEEL = ".whl"
    SOURCE = ".tar.gz"


class DistributionMember(StrEnum):
    """
    The parts of a wheel's ``dist-info`` folder a release is read from.
    """

    METADATA = ".dist-info/METADATA"
    LICENSES = ".dist-info/licenses/"


class RequirementField(StrEnum):
    """
    The metadata field naming one requirement of a distribution.
    """

    REQUIRES_DIST = "Requires-Dist: "


# %% the built files


@dataclass(frozen=True)
class PythonWheel:
    """
    A built Python wheel: the file a distribution is installed from.
    """

    path: Path
    """
    The wheel file.
    """

    @property
    def distribution_name(self) -> str:
        """
        The canonical name of the distribution it is of.
        """
        return canonicalize_name(self.path.name.split("-")[0])

    @property
    def version(self) -> str:
        """
        The version it carries.
        """
        return self.path.name.split("-")[1]

    @property
    def requirements(self) -> list[Requirement]:
        """
        The requirements its metadata declares.
        """
        with zipfile.ZipFile(self.path) as archive:
            (metadata,) = (
                name
                for name in archive.namelist()
                if name.endswith(DistributionMember.METADATA)
            )
            lines = archive.read(metadata).decode("utf-8").splitlines()
        return [
            Requirement(line.removeprefix(RequirementField.REQUIRES_DIST))
            for line in lines
            if line.startswith(RequirementField.REQUIRES_DIST)
        ]

    @property
    def licence(self) -> bytes:
        """
        What the wheel carries of the :attr:`ReleaseFile.LICENSE` file.
        """
        return self.carried_file(ReleaseFile.LICENSE)

    @property
    def notice(self) -> bytes:
        """
        What the wheel carries of the :attr:`ReleaseFile.NOTICE` file.
        """
        return self.carried_file(ReleaseFile.NOTICE)

    def carried_file(self, release_file: ReleaseFile) -> bytes:
        """
        :param release_file: One of the files every distribution carries.
        :return: What the wheel carries of it, under its ``dist-info`` licences.
        """
        with zipfile.ZipFile(self.path) as archive:
            (entry,) = (
                name
                for name in archive.namelist()
                if DistributionMember.LICENSES in name
                and Path(name).name == release_file
            )
            return archive.read(entry)


@dataclass(frozen=True)
class SourceDistribution:
    """
    A built source distribution.
    """

    path: Path
    """
    The archive.
    """

    @property
    def distribution_name(self) -> str:
        """
        The canonical name of the distribution it is of.
        """
        return canonicalize_name(self.path.name.rsplit("-", 1)[0])

    def carries_file_at_root(self, release_file: ReleaseFile) -> bool:
        """
        :param release_file: One of the files every distribution carries.
        :return: Whether it sits at the root of the archive.
        """
        root = self.path.name.removesuffix(DistributionSuffix.SOURCE)
        with tarfile.open(self.path) as archive:
            return f"{root}/{release_file}" in archive.getnames()


@dataclass(frozen=True)
class BuiltRelease:
    """
    The files ``uv build --all-packages`` wrote.
    """

    directory: Path
    """
    Where the wheels and source distributions are.
    """

    @property
    def wheels_by_distribution_name(self) -> dict[str, PythonWheel]:
        """
        The wheels, by the canonical name of the distribution each is of.
        """
        found = (
            PythonWheel(path)
            for path in self.directory.glob(f"*{DistributionSuffix.WHEEL}")
        )
        return {wheel.distribution_name: wheel for wheel in found}

    @property
    def source_distributions_by_distribution_name(
        self,
    ) -> dict[str, SourceDistribution]:
        """
        The source distributions, by the canonical name of the distribution each is of.
        """
        found = (
            SourceDistribution(path)
            for path in self.directory.glob(f"*{DistributionSuffix.SOURCE}")
        )
        return {source.distribution_name: source for source in found}
