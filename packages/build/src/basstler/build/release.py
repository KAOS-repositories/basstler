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


class BasstlerFamily(StrEnum):
    """
    The name every basstler distribution shares, alone or followed by a hyphen and a part.
    """

    NAME = "basstler"

    @classmethod
    def includes(cls, distribution: str) -> bool:
        """
        :param distribution: The name of a distribution.
        :return: Whether it is basstler or one of its parts.
        """
        name = canonicalize_name(distribution)
        return name == cls.NAME or name.startswith(f"{cls.NAME}-")


# %% the built files


@dataclass(frozen=True)
class Wheel:
    """
    A built wheel.
    """

    path: Path
    """
    The wheel file.
    """

    @property
    def distribution(self) -> str:
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

    def licence_file(self, release_file: ReleaseFile) -> bytes:
        """
        :param release_file: One of the files every distribution carries.
        :return: What the wheel carries of it.
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
    def distribution(self) -> str:
        """
        The canonical name of the distribution it is of.
        """
        return canonicalize_name(self.path.name.rsplit("-", 1)[0])

    def carries_at_root(self, release_file: ReleaseFile) -> bool:
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
    def wheels(self) -> dict[str, Wheel]:
        """
        The wheels, by the canonical name of the distribution each is of.
        """
        found = (
            Wheel(path) for path in self.directory.glob(f"*{DistributionSuffix.WHEEL}")
        )
        return {wheel.distribution: wheel for wheel in found}

    @property
    def source_distributions(self) -> dict[str, SourceDistribution]:
        """
        The source distributions, by the canonical name of the distribution each is of.
        """
        found = (
            SourceDistribution(path)
            for path in self.directory.glob(f"*{DistributionSuffix.SOURCE}")
        )
        return {source.distribution: source for source in found}
