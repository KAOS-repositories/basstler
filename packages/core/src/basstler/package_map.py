"""
The distributions this package is split into, the layers they sit in, and which modules
each one ships.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from functools import cached_property
from itertools import combinations
from pathlib import Path
from typing import Annotated, Self

import rustworkx
from pydantic import Field

from basstler.exceptions import (
    InconsistentPackageMap,
    PackageMapInconsistency,
    UndeclaredDistribution,
)
from basstler.json_model import ValidatedJSONModel
from basstler.locations import NamespacePackage, WorkspaceLocation

# %% layers and distributions


class Layer(IntEnum):
    """
    A layer of distributions; a distribution depends only on distributions in its own
    layer or a lower one.
    """

    CORE = 1
    """
    What every other distribution builds on: locations, environment, exceptions.
    """

    LOCAL_TOOLS = 2
    """
    Tools that work on a local checkout alone: git and the code rules.
    """

    GITHUB = 3
    """
    GitHub's data and the client that reads and writes it.
    """

    COLLABORATION = 4
    """
    Work on pull requests: upstream reviews and stacked pull requests.
    """

    NOTES = 5
    """
    The personal notes and their setup.
    """

    PLANS = 6
    """
    Plans and their items, kept on the personal-notes branch.
    """

    USER_FACING = 7
    """
    What a user reads or invokes directly: the plan site hub and the skills.
    """

    MCP = 8
    """
    The Model Context Protocol server.
    """

    META_PACKAGE = 9
    """
    The ``basstler`` distribution, which installs every default distribution.
    """


class Distribution(StrEnum):
    """
    A distribution this package is released as, by its package name, and the layer it
    sits in.
    """

    layer: Layer
    """
    The layer the distribution sits in.
    """

    def __new__(cls, name: str, layer: Layer) -> Self:
        """
        :param name: The distribution's package name, the member's value.
        :param layer: The layer it sits in.
        """
        member = str.__new__(cls, name)
        member._value_ = name
        member.layer = layer
        return member

    BUILD = "basstler-build", Layer.CORE
    """
    The hatch hook every distribution is built with.
    """

    CORE = "basstler-core", Layer.CORE
    """
    The foundation every other distribution imports.
    """

    GIT = "basstler-git", Layer.LOCAL_TOOLS
    """
    Git commands and branches.
    """

    RULES = "basstler-rules", Layer.LOCAL_TOOLS
    """
    The code rules, their checkers and the generated ``AGENTS.md``.
    """

    GITHUB = "basstler-github", Layer.GITHUB
    """
    The GitHub client and the models of GitHub's data.
    """

    REVIEWS = "basstler-reviews", Layer.COLLABORATION
    """
    Reading an upstream pull request's checks and review threads.
    """

    STACK = "basstler-stack", Layer.COLLABORATION
    """
    Stacked pull request maintenance.
    """

    NOTES = "basstler-notes", Layer.NOTES
    """
    Personal notes, pull request progress notes and their setup.
    """

    PLAN = "basstler-plan", Layer.PLANS
    """
    Plans and their items.
    """

    HUB = "basstler-hub", Layer.USER_FACING
    """
    The plan site.
    """

    META_PACKAGE = "basstler", Layer.META_PACKAGE
    """
    The command tree every command is mounted on, installing every default
    distribution.
    """


# %% declarations


@dataclass(frozen=True)
class DistributionDeclaration:
    """
    What one distribution ships and which distributions its ``pyproject.toml`` lists.
    """

    distribution: Distribution
    """
    The distribution declared.
    """

    layer: Layer
    """
    The layer it sits in.
    """

    modules: tuple[str, ...]
    """
    The dotted names, within ``basstler``, of the modules and subpackages it ships; a
    subpackage ships every module under it that a longer name does not claim.
    """

    dependencies: tuple[Distribution, ...] = ()
    """
    The distributions it may import.
    """

    @classmethod
    def read(cls, directory: Path) -> DistributionDeclaration:
        """
        :param directory: A distribution's directory in the workspace.
        :return: The distribution its ``pyproject.toml`` names, shipping every module and
            subpackage of its part of ``basstler``, listing every basstler distribution
            it requires.
        """
        metadata = DistributionMetadata.from_json(
            tomllib.loads(
                (directory / WorkspaceLocation.METADATA).read_text(encoding="utf-8")
            )
        )
        distribution = Distribution(metadata.project.name)
        source = directory / WorkspaceLocation.PACKAGE_SOURCE
        modules = sorted(
            entry.stem
            for entry in source.iterdir()
            if (entry.suffix == ".py" and entry.stem != "__init__")
            or (entry.is_dir() and any(entry.rglob("*.py")))
        )
        names = {member.value for member in Distribution}
        return cls(
            distribution,
            distribution.layer,
            tuple(modules),
            tuple(
                Distribution(name)
                for name in metadata.requirement_names
                if name in names
            ),
        )

    def claim_length(self, module: str) -> int:
        """
        :param module: A module's dotted name within ``basstler``.
        :return: The length of the longest of :attr:`modules` that is *module* or a
            package holding it; zero when none is.
        """
        return max(
            (
                len(claimed)
                for claimed in self.modules
                if module == claimed or module.startswith(f"{claimed}.")
            ),
            default=0,
        )


@dataclass(frozen=True)
class PackageMap(Mapping[Distribution, DistributionDeclaration]):
    """
    The declaration of each distribution, checked to be layered and acyclic.
    """

    declarations: tuple[DistributionDeclaration, ...]
    """
    One declaration per distribution.
    """

    def __post_init__(self) -> None:
        """
        :raise InconsistentPackageMap: When the declarations are not layered and
            acyclic, or two of them claim one module.
        """
        for first, second in combinations(self.declarations, 2):
            if set(first.modules) & set(second.modules):
                raise InconsistentPackageMap(
                    PackageMapInconsistency.MODULE_CLAIMED_TWICE,
                    (first.distribution, second.distribution),
                )
        for declaration in self.declarations:
            for dependency in declaration.dependencies:
                if dependency not in self:
                    raise InconsistentPackageMap(
                        PackageMapInconsistency.UNDECLARED_DISTRIBUTION, (dependency,)
                    )
                if self[dependency].layer > declaration.layer:
                    raise InconsistentPackageMap(
                        PackageMapInconsistency.DEPENDENCY_ON_A_HIGHER_LAYER,
                        (declaration.distribution, dependency),
                    )
        cycle = next(iter(rustworkx.simple_cycles(self.dependency_graph)), None)
        if cycle is not None:
            raise InconsistentPackageMap(
                PackageMapInconsistency.DEPENDENCY_CYCLE,
                tuple(self.dependency_graph[node] for node in cycle),
            )

    def __getitem__(self, distribution: Distribution) -> DistributionDeclaration:
        for declaration in self.declarations:
            if declaration.distribution is distribution:
                return declaration
        raise UndeclaredDistribution(distribution)

    def __iter__(self) -> Iterator[Distribution]:
        return (declaration.distribution for declaration in self.declarations)

    def __len__(self) -> int:
        return len(self.declarations)

    @cached_property
    def dependency_graph(self) -> rustworkx.PyDiGraph:
        """
        The distributions as nodes, with an edge from each to every one it depends on.
        """
        graph = rustworkx.PyDiGraph()
        nodes = {
            declaration.distribution: graph.add_node(declaration.distribution)
            for declaration in self.declarations
        }
        for declaration in self.declarations:
            for dependency in declaration.dependencies:
                graph.add_edge(nodes[declaration.distribution], nodes[dependency], None)
        return graph

    def claiming(self, module: str) -> DistributionDeclaration | None:
        """
        :param module: A module's dotted name within ``basstler``.
        :return: The declaration whose :attr:`DistributionDeclaration.modules` names
            *module* most specifically; none when no declaration names it.
        """
        claim_length, declaration = max(
            (
                (declaration.claim_length(module), declaration)
                for declaration in self.declarations
            ),
            key=lambda claim: claim[0],
        )
        return declaration if claim_length else None


# %% the distributions' metadata

REQUIREMENT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
"""
The distribution name a requirement specifier starts with.
"""


class SiblingPinsSettings(ValidatedJSONModel):
    """
    The settings of the hatch hook pinning a distribution's basstler requirements.
    """

    dependencies: tuple[str, ...] = ()
    """
    The distribution's requirement specifiers, its basstler requirements unpinned.
    """


class MetadataHooks(ValidatedJSONModel):
    """
    The hatch metadata hooks a distribution is built with.
    """

    sibling_pins: Annotated[
        SiblingPinsSettings, Field(alias="basstler-sibling-pins")
    ] = SiblingPinsSettings()
    """
    The hook pinning its basstler requirements to its own version.
    """


class HatchMetadata(ValidatedJSONModel):
    """
    How hatch builds a distribution's metadata.
    """

    hooks: MetadataHooks = MetadataHooks()
    """
    The hooks that fill in the metadata's dynamic fields.
    """


class HatchSettings(ValidatedJSONModel):
    """
    A distribution's hatch settings.
    """

    metadata: HatchMetadata = HatchMetadata()
    """
    How its metadata is built.
    """


class ToolSettings(ValidatedJSONModel):
    """
    The settings of the tools a distribution is built with.
    """

    hatch: HatchSettings = HatchSettings()
    """
    Its hatch settings.
    """


class ProjectTable(ValidatedJSONModel):
    """
    A distribution's ``[project]`` table.
    """

    name: str
    """
    The distribution's package name.
    """

    dependencies: tuple[str, ...] = ()
    """
    The requirement specifiers it states itself, when they are not dynamic.
    """


class DistributionMetadata(ValidatedJSONModel):
    """
    A distribution's ``pyproject.toml``.
    """

    project: ProjectTable
    """
    Its ``[project]`` table.
    """

    tool: ToolSettings = ToolSettings()
    """
    Its ``[tool]`` table.
    """

    @property
    def requirement_names(self) -> tuple[str, ...]:
        """
        The names of the distributions it requires, whether stated in ``[project]`` or
        through the sibling-pins hook.
        """
        return tuple(
            REQUIREMENT_NAME.match(specifier).group()
            for specifier in (
                *self.project.dependencies,
                *self.tool.hatch.metadata.hooks.sibling_pins.dependencies,
            )
        )


# %% the workspace


@dataclass(frozen=True)
class Workspace:
    """
    The uv workspace of basstler's distributions, one directory each under
    ``packages``.
    """

    root: Path
    """
    The workspace's root, holding ``packages``.
    """

    @cached_property
    def package_directories(self) -> tuple[Path, ...]:
        """
        Each distribution's directory, in name order.
        """
        return tuple(
            sorted(
                metadata.parent
                for metadata in (self.root / WorkspaceLocation.PACKAGES).glob(
                    f"*/{WorkspaceLocation.METADATA}"
                )
            )
        )

    @cached_property
    def package_map(self) -> PackageMap:
        """
        The map the distributions' directories and metadata declare.
        """
        return PackageMap(
            tuple(
                DistributionDeclaration.read(directory)
                for directory in self.package_directories
            )
        )

    @cached_property
    def namespace_package(self) -> NamespacePackage:
        """
        Each distribution's part of the ``basstler`` package.
        """
        return NamespacePackage(
            tuple(
                directory / WorkspaceLocation.PACKAGE_SOURCE
                for directory in self.package_directories
            )
        )
