"""
basstler's own project, as the workflows, links and tokens it sets up name it.
"""

from __future__ import annotations

import functools
import importlib.metadata
from enum import StrEnum

from basstler.class_property import classproperty
from basstler.git.branch import Branch
from basstler.github.exceptions import BasstlerSourceUnknown
from basstler.github.repository import Repository
from basstler.locations import PackageLocation
from basstler.package_map import Distribution

# %% the package metadata


class ProjectUrlLabel(StrEnum):
    """
    The labels of the ``Project-URL`` entries ``pyproject.toml`` declares.
    """

    SOURCE = "Source"
    """
    The repository basstler is developed in.
    """


# %% the project


class BasstlerProject:
    """
    Where basstler is developed and released.
    """

    @classproperty
    def name(cls) -> str:
        """
        The package's name, which also names the tokens and commands it sets up.
        """
        return PackageLocation.DIRECTORY.name

    @classproperty
    def repository(cls) -> Repository:
        """
        The repository basstler is developed in, whose reusable workflows users' callers
        run.
        """
        return cls._source_repository(Distribution.GITHUB)

    @classproperty
    def default_branch(cls) -> Branch:
        """
        The branch of :attr:`repository` that holds what is developed next.
        """
        return Branch("main")

    @staticmethod
    @functools.cache
    def _source_repository(distribution: Distribution) -> Repository:
        """
        :param distribution: The installed distribution whose metadata is read.
        :return: The repository its ``Project-URL`` labels as the source.
        :raises BasstlerSourceUnknown: If the metadata names no source.
        """
        entries = importlib.metadata.metadata(distribution).get_all("Project-URL", [])
        for entry in entries:
            label, _, url = entry.partition(", ")
            if label == ProjectUrlLabel.SOURCE:
                return Repository.from_remote_url(url)
        raise BasstlerSourceUnknown(distribution, tuple(entries))
