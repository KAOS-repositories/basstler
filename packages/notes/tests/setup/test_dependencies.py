"""
What the package requires, read from the installed distributions or a declaration, and
which of it this environment is missing.

The expected requirements are read from the workspace's own metadata rather than
restated: what these tests hold is the reading, not the list.
"""

from __future__ import annotations

import tomllib
from importlib.metadata import distributions

import pytest

from basstler.locations import PackageLocation
from basstler.package_map import Distribution, DistributionMetadata, Workspace
from basstler.setup import dependencies
from basstler.setup.dependencies import (
    Dependency,
    DependencyDeclaration,
    InstalledDistribution,
    MalformedDependencyDeclarationError,
    PyprojectKey,
    RequirementSource,
    UnreadableDependencyDeclarationError,
)

from basstler_testing.constants.paths import DatasetLocation
from basstler_testing.project_declaration import ProjectDeclaration
from basstler_testing.script_runner import PythonModuleRunner

# %% the declaration


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
        tomllib.loads(path.read_text(encoding="utf-8"))
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


def test_a_declaration_naming_no_dependencies_is_read_as_needing_none(tmp_path):
    """
    Distinct from unreadable: a package that declares nothing needs nothing, so the
    caller installs nothing rather than being told it could not check.
    """
    declaration = tmp_path / PackageLocation.META_PACKAGE_METADATA.name
    declaration.write_text(
        f'[{PyprojectKey.PROJECT}]\n{PyprojectKey.NAME} = "nothing"\n', encoding="utf-8"
    )

    assert DependencyDeclaration(declaration).dependencies() == ()


@pytest.mark.parametrize(
    ("specifier", "distribution_name"),
    [
        ("nh3>=0.2", "nh3"),
        ("pyyaml >= 6", "pyyaml"),
        ("markdown", "markdown"),
        ("jinja2[i18n]>=3", "jinja2"),
        ("nh3 ; python_version >= '3.11'", "nh3"),
    ],
)
def test_the_distribution_name_is_the_specifier_without_its_constraints(
    specifier: str, distribution_name: str
):
    """
    A specifier carries version bounds, extras and markers; only its name identifies the
    distribution to look up.
    """
    assert Dependency(specifier).distribution_name == distribution_name


# %% what is missing


def test_a_dependency_this_environment_has_is_not_reported_missing():
    """
    The common case the session start turns on: nothing missing means no installer runs.
    """
    installed = Dependency("pytest")

    assert not installed.is_missing


def test_a_distribution_nothing_has_installed_is_reported_missing():
    """
    A name no distribution can answer to, so the check cannot pass by accident.
    """
    absent = Dependency("basstler-no-such-distribution>=1")

    assert absent.is_missing


def test_a_dependency_spelled_differently_from_its_installed_distribution_is_present(
    monkeypatch,
):
    """
    Case and the separators ``-``, ``_`` and ``.`` do not tell distribution names apart,
    so a declaration need not spell a name the way the distribution itself does.
    """
    monkeypatch.syspath_prepend(DatasetLocation.INSTALLED_DISTRIBUTIONS)
    (installed,) = distributions(path=[str(DatasetLocation.INSTALLED_DISTRIBUTIONS)])
    respelled = Dependency(f"{installed.name.upper().replace('_', '-')}>=1")

    assert not respelled.is_missing


def test_the_requirements_are_the_package_itself_then_its_dependencies():
    """
    An environment runs a package only with the package installed in it, so the package
    is the first thing it requires.
    """
    declared = ProjectDeclaration.read(DatasetLocation.PARTLY_INSTALLED_PROJECT.value)

    assert [
        requirement.specifier
        for requirement in DependencyDeclaration(
            DatasetLocation.PARTLY_INSTALLED_PROJECT.value
        ).requirements()
    ] == [declared.name, *declared.dependencies]


def test_a_project_nothing_has_installed_is_reported_missing():
    """
    The package itself counts as missing where its distribution is not installed, even
    with every dependency present.
    """
    declaration = DependencyDeclaration(DatasetLocation.UNINSTALLED_PROJECT.value)

    assert declaration.missing() == (Dependency(declaration.project().specifier),)


def test_missing_requirements_are_a_subset_of_what_is_declared():
    """
    What the caller installs is drawn from the declaration and nothing else.
    """
    missing = DependencyDeclaration(
        DatasetLocation.PARTLY_INSTALLED_PROJECT.value
    ).missing()
    declared = ProjectDeclaration.read(DatasetLocation.PARTLY_INSTALLED_PROJECT.value)

    assert {dependency.specifier for dependency in missing} <= {
        declared.name,
        *declared.dependencies,
    }


def test_an_absent_declaration_raises_rather_than_declaring_nothing(tmp_path):
    """
    An absent file is not an empty declaration: reading nothing from it would tell a
    caller that nothing is missing.
    """
    absent = DependencyDeclaration(
        tmp_path / PackageLocation.META_PACKAGE_METADATA.value.name
    )

    with pytest.raises(UnreadableDependencyDeclarationError):
        absent.missing()


def test_a_declaration_that_is_not_toml_raises_naming_itself(tmp_path):
    """
    A declaration that will not parse is reported as the file it is, so a caller can say
    which file to fix.
    """
    malformed = tmp_path / PackageLocation.META_PACKAGE_METADATA.value.name
    malformed.write_text("this is not toml\n", encoding="utf-8")

    with pytest.raises(MalformedDependencyDeclarationError) as raised:
        DependencyDeclaration(malformed).missing()

    assert raised.value.declaration == malformed


# %% an installed copy, which carries no pyproject.toml


def test_an_installed_distribution_this_environment_has_misses_nothing():
    """
    The suite's own environment has the package installed with everything it needs.
    """
    assert InstalledDistribution(Distribution.META_PACKAGE.value).missing() == ()


def test_a_distribution_nothing_installed_is_missing_itself():
    """
    With nothing installed there are no dependencies to read, and the package itself is
    what is missing.
    """
    absent = InstalledDistribution("a-distribution-nothing-installed")

    assert absent.missing() == (Dependency(absent.name),)


# %% the command line the shell calls


def run_module(*arguments: str):
    """
    Run this module as the shell does, from the repository root.

    :param arguments: Arguments to the module.
    :return: The completed process, with output captured as text.
    """
    return PythonModuleRunner(
        project_root=PackageLocation.SOURCE_TREE.value,
        module_name=dependencies.__name__,
    ).run(*arguments)


def test_the_command_line_prints_one_specifier_per_missing_requirement():
    """
    The output is what a caller passes straight to ``pip install``, so it carries the
    version constraints rather than bare names.
    """
    result = run_module()

    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == [
        dependency.specifier
        for dependency in RequirementSource.for_this_package().missing()
    ]


def test_the_command_line_answers_help():
    """
    Every entry point of this package answers ``--help``; this one is called by a hook
    that has to be able to tell a broken invocation from a satisfied one.
    """
    result = run_module("--help")

    assert result.returncode == 0, result.stderr


def test_an_unreadable_declaration_fails_rather_than_reporting_nothing_missing():
    """
    A missing or unparseable ``pyproject.toml`` must not look like a satisfied
    environment: the caller reports that it could not check instead of installing
    nothing.
    """
    result = PythonModuleRunner(
        project_root=PackageLocation.SOURCE_TREE.value,
        module_name=dependencies.__name__,
    ).run("--declaration", "/nonexistent/pyproject.toml")

    assert result.returncode != 0
    assert result.stdout.strip() == ""
