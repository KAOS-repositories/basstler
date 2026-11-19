"""
Tests for :mod:`basstler.package_map`: the declared distributions, their layers and the
modules each one claims.
"""

from __future__ import annotations

import pytest

from basstler.exceptions import (
    InconsistentPackageMap,
    PackageMapInconsistency,
    UndeclaredDistribution,
)
from basstler.package_layout import package_modules
from basstler.locations import PackageLocation
from basstler.package_map import (
    Distribution,
    DistributionDeclaration,
    Layer,
    PackageMap,
    Workspace,
)

from basstler_testing.constants.paths import PackageBoundarySnippet

# %% the workspace's map


@pytest.fixture
def package_map() -> PackageMap:
    """
    :return: The map this checkout's distributions declare.
    """
    return Workspace(PackageLocation.SOURCE_TREE.value).package_map


def test_every_module_of_the_package_is_claimed(package_map):
    """
    Every installed module sits in the part of ``basstler`` of a distribution of the
    workspace.
    """
    unclaimed = [
        module.name
        for module in package_modules()
        if package_map.claiming(module.name) is None
    ]

    assert unclaimed == []


def test_a_distribution_ships_its_part_and_lists_what_its_metadata_requires():
    """
    The lower distribution of the dataset's workspace ships ``low`` and lists nothing;
    the higher one ships ``high`` and lists the lower one.
    """
    package_map = Workspace(PackageBoundarySnippet.DIRECTORY.value).package_map

    assert package_map.declarations == (
        DistributionDeclaration(
            Distribution.GIT, Distribution.GIT.layer, ("high",), (Distribution.CORE,)
        ),
        DistributionDeclaration(Distribution.CORE, Distribution.CORE.layer, ("low",)),
    )


# %% looking up a declaration


def test_the_map_holds_each_declaration_under_its_distribution(package_map):
    """
    The map reads like the mapping it is, from a distribution to its declaration.
    """
    assert dict(package_map) == {
        declaration.distribution: declaration
        for declaration in package_map.declarations
    }


def test_an_undeclared_distribution_is_not_in_the_map():
    """
    A lookup of a distribution nothing declares finds no declaration.
    """
    package_map = PackageMap(
        (DistributionDeclaration(Distribution.CORE, Layer.CORE, ("core",)),)
    )

    assert package_map.get(Distribution.GIT) is None


def test_a_lookup_of_an_undeclared_distribution_names_it():
    """
    Reading the declaration of a distribution nothing declares raises the error naming
    it.
    """
    package_map = PackageMap(
        (DistributionDeclaration(Distribution.CORE, Layer.CORE, ("core",)),)
    )

    with pytest.raises(UndeclaredDistribution) as raised:
        package_map[Distribution.GIT]

    assert raised.value.distribution is Distribution.GIT


# %% claiming


def test_the_most_specific_claim_wins():
    """
    A module named by one declaration, inside a subpackage another declares, belongs to
    the first.
    """
    subpackage = DistributionDeclaration(Distribution.STACK, Layer.CORE, ("tools",))
    module = DistributionDeclaration(Distribution.GIT, Layer.CORE, ("tools.git",))
    package_map = PackageMap((subpackage, module))

    assert package_map.claiming("tools.git.commands") is module
    assert package_map.claiming("tools.other") is subpackage


def test_a_name_sharing_only_a_prefix_is_not_claimed():
    """
    Claiming ``tools`` claims ``tools.git`` but not ``toolset``.
    """
    package_map = PackageMap(
        (DistributionDeclaration(Distribution.CORE, Layer.CORE, ("tools",)),)
    )

    assert package_map.claiming("toolset") is None


# %% inconsistencies


def test_a_dependency_on_a_higher_layer_is_refused():
    """
    A core distribution cannot list one that sits above it.
    """
    with pytest.raises(InconsistentPackageMap) as raised:
        PackageMap(
            (
                DistributionDeclaration(
                    Distribution.CORE, Layer.CORE, ("low",), (Distribution.GITHUB,)
                ),
                DistributionDeclaration(Distribution.GITHUB, Layer.GITHUB, ("high",)),
            )
        )

    assert raised.value.inconsistency is (
        PackageMapInconsistency.DEPENDENCY_ON_A_HIGHER_LAYER
    )


def test_a_cycle_within_a_layer_is_refused():
    """
    Two distributions of one layer cannot list each other.
    """
    with pytest.raises(InconsistentPackageMap) as raised:
        PackageMap(
            (
                DistributionDeclaration(
                    Distribution.GIT, Layer.LOCAL_TOOLS, ("git",), (Distribution.RULES,)
                ),
                DistributionDeclaration(
                    Distribution.RULES,
                    Layer.LOCAL_TOOLS,
                    ("rules",),
                    (Distribution.GIT,),
                ),
            )
        )

    assert raised.value.inconsistency is PackageMapInconsistency.DEPENDENCY_CYCLE


def test_a_dependency_on_an_undeclared_distribution_is_refused():
    """
    A listed distribution has to be declared itself.
    """
    with pytest.raises(InconsistentPackageMap) as raised:
        PackageMap(
            (
                DistributionDeclaration(
                    Distribution.GIT, Layer.LOCAL_TOOLS, ("git",), (Distribution.CORE,)
                ),
            )
        )

    assert raised.value.inconsistency is (
        PackageMapInconsistency.UNDECLARED_DISTRIBUTION
    )


def test_a_module_claimed_twice_is_refused():
    """
    Two distributions cannot both ship one module.
    """
    with pytest.raises(InconsistentPackageMap) as raised:
        PackageMap(
            (
                DistributionDeclaration(Distribution.CORE, Layer.CORE, ("shared",)),
                DistributionDeclaration(
                    Distribution.GIT, Layer.LOCAL_TOOLS, ("shared",)
                ),
            )
        )

    assert raised.value.inconsistency is PackageMapInconsistency.MODULE_CLAIMED_TWICE
