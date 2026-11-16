"""
Tools an experiment compares, each installed from PyPI into a virtual environment of its
own, so its size and dependencies can be measured apart from everything else.
"""

from __future__ import annotations

import importlib.metadata
import sys
from dataclasses import dataclass
from pathlib import Path

from basstler.command_run import CommandRun
from basstler.experiments.measurement import BYTES_PER_MEGABYTE

INSTALLER_DISTRIBUTIONS = frozenset({"pip", "setuptools"})
"""
The distributions a new virtual environment holds before any tool is installed.
"""

WINDOWS_PLATFORM = "win32"
"""
The platform whose virtual environments keep their programs in ``Scripts``.
"""

# %% the installation's footprint


@dataclass(frozen=True)
class InstallFootprint:
    """
    What installing a tool adds to a fresh virtual environment.
    """

    version: str
    """
    The version of the tool installed.
    """

    megabytes: float
    """
    The disk space the tool, its dependencies and the files it downloads on its first
    run take.
    """

    dependencies: tuple[str, ...]
    """
    The distributions installed with it, by name.
    """


# %% one installation


@dataclass(frozen=True)
class ToolInstallation:
    """
    One tool from PyPI in a virtual environment of its own.
    """

    distribution: str
    """
    The distribution installed, as PyPI names it.
    """

    directory: Path
    """
    The virtual environment it is installed in.
    """

    extras: tuple[str, ...] = ()
    """
    The optional features installed with it.
    """

    downloads: tuple[Path, ...] = ()
    """
    Directories, under :attr:`directory`, the tool fills on its first run.
    """

    @property
    def programs(self) -> Path:
        """
        The directory holding the environment's programs.
        """
        if sys.platform == WINDOWS_PLATFORM:
            return self.directory / "Scripts"
        return self.directory / "bin"

    def program(self, name: str) -> Path:
        """
        :param name: The name of a program the tool installs.
        :return: Its path.
        """
        suffix = ".exe" if sys.platform == WINDOWS_PLATFORM else ""
        return self.programs / f"{name}{suffix}"

    @property
    def python(self) -> Path:
        """
        The environment's interpreter.
        """
        return self.program("python")

    @property
    def requirement(self) -> str:
        """
        What the installer is asked for: the distribution with its extras.
        """
        if not self.extras:
            return self.distribution
        return f"{self.distribution}[{','.join(self.extras)}]"

    def install(self) -> None:
        """
        Create the environment and install the latest release of the tool in it, unless
        it already is.

        :raises CommandFailed: If either step fails.
        """
        if self.python.exists():
            return
        creation = [sys.executable, "-m", "venv", str(self.directory)]
        CommandRun.of(creation).finished()
        installation = [
            str(self.python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--quiet",
            self.requirement,
        ]
        CommandRun.of(installation).finished()

    def footprint(self) -> InstallFootprint:
        """
        :return: What the installation added, measured from the environment's records
            of each installed file.
        """
        site_packages = next(self.directory.glob("**/site-packages"))
        installed = [
            installed
            for installed in importlib.metadata.distributions(path=[str(site_packages)])
            if installed.metadata["Name"].lower() not in INSTALLER_DISTRIBUTIONS
        ]
        recorded = sum(
            (site_packages / file).stat().st_size
            for installed_distribution in installed
            for file in installed_distribution.files or ()
            if (site_packages / file).is_file()
        )
        downloaded = sum(
            file.stat().st_size
            for download in self.downloads
            for file in download.rglob("*")
            if file.is_file()
        )
        tool = next(
            installed_distribution
            for installed_distribution in installed
            if installed_distribution.metadata["Name"].lower()
            == self.distribution.lower()
        )
        return InstallFootprint(
            version=tool.version,
            megabytes=(recorded + downloaded) / BYTES_PER_MEGABYTE,
            dependencies=tuple(
                sorted(
                    installed_distribution.metadata["Name"]
                    for installed_distribution in installed
                    if installed_distribution is not tool
                )
            ),
        )
