"""
Tests for :mod:`basstler.package_map`: the declared distributions, their layers and the
modules each one claims.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Annotated

import pytest
import rustworkx
from pydantic import Field

from basstler.exceptions import (
    InconsistentPackageMap,
    PackageMapInconsistency,
    UndeclaredDistribution,
)
from basstler.package_layout import package_modules
from basstler.locations import PackageLocation
from basstler.package_map import (
    REQUIREMENT_NAME,
    Distribution,
    DistributionDeclaration,
    Layer,
    PackageMap,
    Workspace,
)
from basstler.json_model import ValidatedJSONModel
from basstler.locations import WorkspaceLocation

from basstler_testing.constants.paths import (
    PackageBoundarySnippet,
    ThirdPartyImportSnippet,
)

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


# %% what each distribution's tests need


class DependencyGroups(ValidatedJSONModel):
    """
    A distribution's ``[dependency-groups]`` table.
    """

    development: Annotated[tuple[str, ...], Field(alias="dev")] = ()
    """
    The requirement specifiers its tests need besides the distribution itself.
    """


class DevelopmentRequirements(ValidatedJSONModel):
    """
    The part of a distribution's ``pyproject.toml`` that says what its tests need.
    """

    dependency_groups: Annotated[DependencyGroups, Field(alias="dependency-groups")] = (
        DependencyGroups()
    )
    """
    Its dependency groups.
    """

    @classmethod
    def read(cls, directory: Path) -> DevelopmentRequirements:
        """
        :param directory: A distribution's directory in the workspace.
        :return: What its ``pyproject.toml`` lists for its tests.
        """
        return cls.from_json(
            tomllib.loads(
                (directory / WorkspaceLocation.METADATA).read_text(encoding="utf-8")
            )
        )


WORKSPACE = Workspace(PackageLocation.SOURCE_TREE.value)
"""
This checkout's workspace.
"""

TESTED_ALONE = [
    (directory, declaration.distribution)
    for directory, declaration in zip(
        WORKSPACE.package_directories, WORKSPACE.package_map.declarations, strict=True
    )
    if declaration.distribution is not Distribution.META_PACKAGE
]
"""
Each distribution whose tests run in an environment of their own, with its directory;
the meta-package's tests cover the whole workspace, its build tooling included.
"""


@pytest.mark.parametrize(
    ("directory", "distribution"),
    TESTED_ALONE,
    ids=lambda value: value.name if isinstance(value, Path) else "",
)
def test_a_distributions_tests_need_no_distribution_it_does_not_require(
    directory, distribution
):
    """
    The basstler distributions a distribution's ``dev`` group lists are ones it
    requires, directly or through another, so its tests run in an environment of its
    own.
    """
    package_map = WORKSPACE.package_map
    node = next(
        index
        for index in package_map.dependency_graph.node_indices()
        if package_map.dependency_graph[index] is distribution
    )
    required = {
        package_map.dependency_graph[index]
        for index in rustworkx.descendants(package_map.dependency_graph, node)
    }
    names = {member.value for member in Distribution}

    assert {
        Distribution(name)
        for name in (
            REQUIREMENT_NAME.match(specifier).group()
            for specifier in DevelopmentRequirements.read(
                directory
            ).dependency_groups.development
        )
        if name in names
    } - required == set()


# %% required libraries


@pytest.fixture
def library_package_map() -> PackageMap:
    """
    :return: The map of the dataset's workspace, whose lower distribution requires
        ``pydantic``.
    """
    return Workspace(ThirdPartyImportSnippet.DIRECTORY.value).package_map


def test_a_distribution_lists_the_libraries_its_metadata_requires(library_package_map):
    """
    The lower distribution lists ``pydantic``, whose version constraint is not part of
    the name; the higher one lists no library of its own.
    """
    assert {
        declaration.distribution: declaration.libraries
        for declaration in library_package_map.declarations
    } == {Distribution.CORE: ("pydantic",), Distribution.GIT: ()}


def test_a_distribution_requires_the_libraries_of_the_distributions_it_lists(
    library_package_map,
):
    """
    The higher distribution lists no library, yet needs the lower one's.
    """
    assert library_package_map.libraries_required_by_distribution(Distribution.GIT) == {
        "pydantic"
    }


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


# %% the name a requirement starts with


@pytest.mark.parametrize(
    ("specifier", "name"),
    [
        ("pydantic>=2", "pydantic"),
        ("basstler-core", "basstler-core"),
        ("ruamel.yaml==0.18", "ruamel.yaml"),
        ("Jinja2", "Jinja2"),
        ("typing_extensions>=4.9 ; python_version<'3.13'", "typing_extensions"),
    ],
)
def test_a_requirement_specifier_starts_with_its_distribution_name(
    specifier: str, name: str
):
    """
    Each specifier is listed beside the name read off its start.
    """
    assert REQUIREMENT_NAME.match(specifier).group() == name


@pytest.mark.parametrize("specifier", ["-pydantic", "_name", ">=2", ""])
def test_a_specifier_not_starting_with_a_letter_or_digit_has_no_name(specifier: str):
    """
    A distribution name starts with a letter or a digit.
    """
    assert REQUIREMENT_NAME.match(specifier) is None
