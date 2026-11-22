"""
What the installed package and its distributions require, read from their metadata and
from the workspace's declarations.
"""

from __future__ import annotations

import tomllib

from basstler.locations import PackageLocation
from basstler.package_map import Distribution, DistributionMetadata, Workspace
from basstler.setup.dependencies import (
    Dependency,
    InstalledDistribution,
    RequirementSource,
)
from basstler.text_file import TextFile

# %% the package's requirements


def installed_requirement_names(name: str) -> list[str]:
    """
    :param name: An installed distribution.
    :return: The name of each requirement it has, in order.
    """
    return [
        requirement.distribution_name
        for requirement in InstalledDistribution(name).requirements()
    ]


def test_the_package_requires_every_distribution_the_command_tree_reaches():
    """
    The ``basstler`` distribution requires each distribution its metadata lists, and
    each of those what its own lists, down to the core.
    """
    package_map = Workspace(PackageLocation.SOURCE_TREE.value).package_map
    reached = set(reachable_distributions(package_map, Distribution.META_PACKAGE))

    assert {
        name
        for name in installed_requirement_names(Distribution.META_PACKAGE.value)
        if Dependency(name).is_basstler_distribution
    } == {distribution.value for distribution in reached}


def test_a_checkout_requires_what_its_declarations_reach_from_the_command_tree():
    """
    Run from a checkout, the package requires what the workspace's declarations list, so
    a dependency a pull adds is missing before anything reinstalls the package.
    """
    package_map = Workspace(PackageLocation.SOURCE_TREE.value).package_map
    reached = reachable_distributions(package_map, Distribution.META_PACKAGE)

    assert {
        requirement.distribution_name
        for requirement in RequirementSource.for_this_package().requirements()
        if requirement.is_basstler_distribution
    } == {distribution.value for distribution in reached}


def test_an_installed_distribution_requires_what_its_metadata_and_its_siblings_list():
    """
    The git distribution requires itself, the core distribution it lists, and what the
    core distribution's own metadata lists.
    """
    git, core = (
        PackageLocation.SOURCE_TREE.value / "packages" / part / "pyproject.toml"
        for part in ("git", "core")
    )

    assert installed_requirement_names(Distribution.GIT.value) == [
        Distribution.GIT.value,
        *metadata_requirement_names(git),
        *metadata_requirement_names(core),
    ]


def metadata_requirement_names(path) -> tuple[str, ...]:
    """
    :param path: A distribution's ``pyproject.toml``.
    :return: The names of the requirements it lists.
    """
    return DistributionMetadata.from_json(
        tomllib.loads(TextFile(path).read())
    ).requirement_names


def reachable_distributions(
    package_map, distribution: Distribution
) -> set[Distribution]:
    """
    :param package_map: The workspace's map.
    :param distribution: Where to start.
    :return: *distribution* and every distribution it lists, directly or through
        another.
    """
    reached = {distribution}
    for dependency in package_map[distribution].dependencies:
        reached |= reachable_distributions(package_map, dependency)
    return reached


def test_an_installed_distribution_this_environment_has_misses_nothing():
    """
    The suite's own environment has the package installed with everything it needs.
    """
    assert InstalledDistribution(Distribution.META_PACKAGE.value).missing() == ()
