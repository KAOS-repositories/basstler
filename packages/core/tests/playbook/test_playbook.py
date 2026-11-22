"""
Tests for :mod:`basstler.playbook.playbook` and :mod:`basstler.playbook.contribution`.
"""

from __future__ import annotations

from importlib.metadata import EntryPoint

import pytest
from basstler_testing.constants.paths import PlaybookSnippet

from basstler.playbook import contribution
from basstler.playbook.contribution import (
    ContributionEntryPointGroup,
    PackageContribution,
)
from basstler.playbook.core_contribution import CoreContribution
from basstler.playbook.exceptions import ComponentNotInPlaybook, PlaybookNotDeclared
from basstler.playbook.playbook import DefaultPlaybook, Playbook, PlaybookFile

from .components import (
    EarlierContribution,
    LabelledComponent,
    LaterContribution,
    OtherKindComponent,
)

FIRST = LabelledComponent("first")
"""
A component every playbook below starts with.
"""

SECOND = OtherKindComponent("second")
"""
A component of another kind every playbook below starts with.
"""

# %% building a playbook


def test_with_components_adds_them_after_the_components_held():
    """
    Added components come last, after those already held.
    """
    added = LabelledComponent("added")

    assert Playbook((FIRST, SECOND)).with_components(added) == Playbook(
        (FIRST, SECOND, added)
    )


def test_without_leaves_out_only_the_components_given():
    """
    Leaving one component out keeps every other one.
    """
    assert Playbook((FIRST, SECOND)).without_components(FIRST) == Playbook((SECOND,))


def test_without_refuses_a_component_the_playbook_does_not_hold():
    """
    Leaving out a component the playbook lacks is a mistake, not a no-op.
    """
    with pytest.raises(ComponentNotInPlaybook):
        Playbook((FIRST,)).without_components(SECOND)


def test_components_of_lists_only_that_kind_in_order():
    """
    Asking for one kind skips the other kinds and keeps the order.
    """
    later = LabelledComponent("later")

    assert Playbook((FIRST, SECOND, later)).components_of(LabelledComponent) == (
        FIRST,
        later,
    )


# %% the default playbook


@pytest.fixture
def two_registered_contributions(monkeypatch):
    """
    Register :class:`LaterContribution` before :class:`EarlierContribution`, under entry
    point names sorting the other way.
    """
    registered = [
        EntryPoint(
            "b-later",
            f"{LaterContribution.__module__}:{LaterContribution.__name__}",
            ContributionEntryPointGroup.CONTRIBUTIONS,
        ),
        EntryPoint(
            "a-earlier",
            f"{EarlierContribution.__module__}:{EarlierContribution.__name__}",
            ContributionEntryPointGroup.CONTRIBUTIONS,
        ),
    ]
    monkeypatch.setattr(
        contribution,
        contribution.entry_points.__name__,
        lambda group: (
            registered if group == ContributionEntryPointGroup.CONTRIBUTIONS else []
        ),
    )


@pytest.mark.usefixtures("two_registered_contributions")
def test_installed_contributions_come_in_entry_point_name_order():
    """
    Contributions are ordered by entry point name, not registration order.
    """
    assert PackageContribution.installed_package_contributions() == (
        EarlierContribution,
        LaterContribution,
    )


@pytest.mark.usefixtures("two_registered_contributions")
def test_the_default_playbook_holds_every_installed_contribution_in_order():
    """
    The default playbook is every installed contribution's components, in order.
    """
    assert DefaultPlaybook().components == (
        *EarlierContribution.playbook_components,
        *LaterContribution.playbook_components,
    )


def test_the_installed_contributions_include_the_core_one():
    """
    Basstler-core registers its own contribution.
    """
    assert CoreContribution in PackageContribution.installed_package_contributions()


# %% a project's own playbook


@pytest.mark.usefixtures("two_registered_contributions")
def test_a_project_without_a_playbook_module_runs_the_default_playbook(tmp_path):
    """
    A project with no playbook module runs every installed contribution.
    """
    assert PlaybookFile(tmp_path).read() == DefaultPlaybook()


def test_a_project_runs_the_playbook_its_module_declares():
    """
    A project's playbook module decides the playbook.
    """
    assert PlaybookFile(PlaybookSnippet.DECLARED).read() == Playbook(
        CoreContribution.playbook_components
    )


def test_a_playbook_module_declaring_no_playbook_is_refused():
    """
    A playbook module that assigns no playbook is refused rather than ignored.
    """
    with pytest.raises(PlaybookNotDeclared):
        PlaybookFile(PlaybookSnippet.UNDECLARED).read()
