"""
Tests for basstler.plan.handover and its command: handing plans over from one personal-
notes branch and taking them on in another.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from basstler.locations import PlanHandoverLocation, ProjectLocation
from basstler.plan import handover_command
from basstler.plan.dependencies import DependencyReference
from basstler.plan.exceptions import (
    HandoverPlanCycleError,
    PlanAlreadyTrackedError,
    PlanOutsideHandoverError,
)
from basstler.plan.handover import HandoverGuide, HandoverPlan, PlanHandover
from basstler.plan.model import ManifestKey, PlanDocument, PlanManifest
from basstler.plan.repository_rules import RepositoryRules

from ..scratch_repository import ScratchRepository
from .conftest import RECEIVERS_FORK, HandedOverPlan

# %% the dataset handover


def plan_named(handover: PlanHandover, identifier: str) -> HandoverPlan:
    """
    :param handover: A handover.
    :param identifier: The id of one of its plans.
    :return: That plan.
    """
    return next(plan for plan in handover.plans if plan.identifier == identifier)


# %% which plans go together


def test_a_plan_is_handed_over_only_with_the_plans_it_depends_on(
    dataset_handover: PlanHandover,
):
    """
    A plan depending on an item of a plan left out could never resolve it after an
    import.
    """
    with pytest.raises(PlanOutsideHandoverError):
        PlanHandover(
            plans=(plan_named(dataset_handover, HandedOverPlan.DOWNSTREAM),),
            progress_notes={},
            repository_rules=RepositoryRules(),
        )


def test_plans_depending_on_each_other_in_a_cycle_are_refused(
    dataset_handover: PlanHandover,
):
    """
    No plan of a cycle can be saved before the plan it names, so the handover is
    refused.
    """
    upstream = plan_named(dataset_handover, HandedOverPlan.UPSTREAM)
    downstream = plan_named(dataset_handover, HandedOverPlan.DOWNSTREAM)
    first, *rest = upstream.manifest.items
    depending_back = {
        **first.content,
        ManifestKey.DEPENDS_ON.key: [
            DependencyReference(
                item_identifier=downstream.manifest.items[0].identifier,
                plan_id=downstream.identifier,
            ).text
        ],
    }
    cyclic_upstream = HandoverPlan(
        manifest=PlanManifest(
            {
                **upstream.manifest.content,
                ManifestKey.ITEMS.key: [
                    depending_back,
                    *(item.content for item in rest),
                ],
            }
        ),
        roadmap_text=upstream.roadmap_text,
    )

    with pytest.raises(HandoverPlanCycleError):
        PlanHandover(
            plans=(cyclic_upstream, downstream),
            progress_notes={},
            repository_rules=RepositoryRules(),
        )


def test_plans_are_saved_after_the_plans_they_depend_on(
    dataset_handover: PlanHandover,
):
    """
    A plan is saved after the plan it depends on, so its cross-plan dependency resolves.
    """
    assert [plan.identifier for plan in dataset_handover.plans_in_saving_order] == [
        HandedOverPlan.UPSTREAM,
        HandedOverPlan.DOWNSTREAM,
    ]


# %% what a plan carries


def test_a_handed_over_plan_names_no_session_and_keeps_everything_else(
    dataset_handover: PlanHandover,
):
    """
    Only the person who ran a session can open it, so the handover drops it alone.
    """
    upstream = plan_named(dataset_handover, HandedOverPlan.UPSTREAM)

    assert [item.content for item in upstream.without_sessions().manifest.items] == [
        {
            key: value
            for key, value in item.content.items()
            if key != ManifestKey.SESSION.key
        }
        for item in upstream.manifest.items
    ]


def test_a_dependency_on_another_plans_item_links_that_items_section(
    dataset_handover: PlanHandover,
):
    """
    The guide links a cross-plan dependency to the section of the item it names.
    """
    upstream = plan_named(dataset_handover, HandedOverPlan.UPSTREAM)
    downstream = plan_named(dataset_handover, HandedOverPlan.DOWNSTREAM)
    (dependency,) = downstream.manifest.items[0].dependencies

    assert downstream.item_anchor(reference_text=dependency) == upstream.item_anchor(
        reference_text=DependencyReference.from_text(dependency).item_identifier
    )


# %% the directory and its guide


def test_a_written_handover_reads_back_as_it_was_written(
    dataset_handover: PlanHandover, tmp_path: Path
):
    """
    Writing a handover and reading it back loses nothing.
    """
    dataset_handover.write(tmp_path)

    assert PlanHandover.from_directory(tmp_path) == dataset_handover


def test_the_guide_gives_every_item_a_section_and_links_its_pull_request(
    dataset_handover: PlanHandover,
):
    """
    Every item has a section to link to, with its pull request where it has one.
    """
    guide = HandoverGuide(handover=dataset_handover).render()

    for plan in dataset_handover.plans:
        for item in plan.manifest.items:
            assert (
                f'<a id="{plan.item_anchor(reference_text=item.identifier)}"></a>'
                in guide
            )
            if item.pull_request_number is not None:
                assert (
                    plan.manifest.repository_of(item).pull_request_url(
                        item.pull_request_number
                    )
                    in guide
                )


# %% exporting


def test_an_export_reads_the_plans_without_sessions_and_only_their_progress_notes(
    exporting_repository: ScratchRepository, dataset_handover: PlanHandover
):
    """
    An export carries the named plans, the progress notes of their items' branches
    alone, and the repository's rules.
    """
    identifiers = [HandedOverPlan.UPSTREAM, HandedOverPlan.DOWNSTREAM]

    exported = PlanHandover.from_notes_branch(
        project_root=exporting_repository.project_root,
        plan_identifiers=identifiers,
    )

    assert exported == PlanHandover(
        plans=tuple(
            plan_named(dataset_handover, identifier).without_sessions()
            for identifier in identifiers
        ),
        progress_notes=dataset_handover.progress_notes,
        repository_rules=dataset_handover.repository_rules,
    )


def test_the_export_command_writes_the_handover_with_its_guide(
    exporting_repository: ScratchRepository,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    The command writes the handover and the guide rendered from it.
    """
    monkeypatch.chdir(exporting_repository.project_root)
    output = tmp_path / "handover"

    handover_command.export_plans(list(HandedOverPlan), output=output)

    assert (output / PlanHandoverLocation.GUIDE).read_text() == HandoverGuide(
        handover=PlanHandover.from_directory(output)
    ).render()


# %% importing


def test_an_import_saves_every_plan_progress_note_and_rule_onto_the_notes_branch(
    receiving_repository: ScratchRepository,
    dataset_handover: PlanHandover,
    tmp_path: Path,
):
    """
    An import leaves the notes branch holding every plan, progress note and rule as
    handed over.
    """
    dataset_handover.save_to_notes_branch(
        project_root=receiving_repository.project_root
    )

    checkout = receiving_repository.clone_notes_branch(tmp_path / "notes")
    assert {
        plan.identifier: (
            PlanManifest.from_file(
                checkout
                / PlanDocument.MANIFEST.path_within_notes_branch(plan.identifier)
            ).content,
            (
                checkout
                / PlanDocument.ROADMAP.path_within_notes_branch(plan.identifier)
            ).read_text(),
        )
        for plan in dataset_handover.plans
    } == {
        plan.identifier: (plan.manifest.content, plan.roadmap_text)
        for plan in dataset_handover.plans
    }
    assert {
        branch: (
            checkout
            / ProjectLocation.PULL_REQUEST_PROGRESS
            / PlanHandover.progress_note_path(branch)
        ).read_text()
        for branch in dataset_handover.progress_notes
    } == dataset_handover.progress_notes
    assert (
        RepositoryRules.from_file(checkout / ProjectLocation.PLAN_RULES)
        == dataset_handover.repository_rules
    )


def test_an_import_refuses_a_plan_the_notes_branch_already_holds_and_saves_nothing(
    exporting_repository: ScratchRepository,
    dataset_handover: PlanHandover,
    tmp_path: Path,
):
    """
    An import never overwrites a plan the receiver already tracks, and saves none of the
    others.
    """
    upstream = plan_named(dataset_handover, HandedOverPlan.UPSTREAM)
    exporting_repository.remove_from_notes_branch(
        PlanDocument.MANIFEST.path_within_notes_branch(HandedOverPlan.DOWNSTREAM)
    )

    with pytest.raises(PlanAlreadyTrackedError):
        dataset_handover.save_to_notes_branch(
            project_root=exporting_repository.project_root
        )

    checkout = exporting_repository.clone_notes_branch(tmp_path / "notes")
    assert [
        path.parent.name
        for path in (checkout / ProjectLocation.PLANS).glob(
            f"*/{PlanDocument.MANIFEST.value}"
        )
    ] == [upstream.identifier]


# %% moving onto the receiver's repository


def test_a_plan_rehomed_keeps_its_started_items_where_their_work_is(
    dataset_handover: PlanHandover,
):
    """
    Items with a branch or pull request stay on the repository they are on, items not
    started follow the new default, and the tracking issue, a number on the old default,
    is dropped.
    """
    upstream = plan_named(dataset_handover, HandedOverPlan.UPSTREAM)

    rehomed = upstream.rehomed(RECEIVERS_FORK).manifest

    assert rehomed.default_repository == RECEIVERS_FORK
    assert [rehomed.repository_of(item) for item in rehomed.items] == [
        upstream.manifest.default_repository
        if item.branch or item.pull_request_number is not None
        else RECEIVERS_FORK
        for item in upstream.manifest.items
    ]
    assert ManifestKey.TRACKING_ISSUE.key not in rehomed.content


def test_a_plan_already_on_the_receivers_repository_is_not_rehomed(
    dataset_handover: PlanHandover,
):
    """
    A receiver pushing to the sender's repository takes the plan over unchanged.
    """
    upstream = plan_named(dataset_handover, HandedOverPlan.UPSTREAM)

    assert upstream.rehomed(upstream.manifest.default_repository) == upstream
