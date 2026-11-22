"""
Tests for exporting a plan handover from a notes branch and importing it onto another,
through the plugin's plan saving.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from basstler.locations import PlanHandoverLocation, ProjectLocation
from basstler.plan import handover_command
from basstler.plan.dependencies import DependencyReference
from basstler.plan.exceptions import (
    PlanAlreadyTrackedError,
    PlanStillNamedError,
)
from basstler.plan.handover import HandoverGuide, PlanHandover
from basstler.plan.model import PlanDocument, PlanManifest
from basstler.plan.repository_rules import RepositoryRules

from basstler_testing.scratch_repository import ScratchRepository
from basstler_testing.plan.handover import (
    plan_named,
    UNRELATED_BRANCH,
    HandedOverPlan,
)
from basstler.text_file import TextFile

# %% exporting and importing through the notes branch


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

    assert (
        TextFile(output / PlanHandoverLocation.GUIDE).read()
        == HandoverGuide(handover=PlanHandover.from_directory(output)).render()
    )


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
            TextFile(
                checkout
                / PlanDocument.ROADMAP.path_within_notes_branch(plan.identifier)
            ).read(),
        )
        for plan in dataset_handover.plans
    } == {
        plan.identifier: (plan.manifest.content, plan.roadmap_text)
        for plan in dataset_handover.plans
    }
    assert {
        branch: TextFile(
            checkout
            / ProjectLocation.PULL_REQUEST_PROGRESS
            / PlanHandover.progress_note_path(branch)
        ).read()
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


def test_removing_handed_over_plans_leaves_only_what_they_do_not_carry(
    exporting_repository: ScratchRepository, tmp_path: Path
):
    """
    Removing the plans deletes them and their items' progress notes from the notes
    branch, and keeps the progress note of a branch no plan names.
    """
    handover = PlanHandover.from_notes_branch(
        project_root=exporting_repository.project_root,
        plan_identifiers=list(HandedOverPlan),
    )

    handover.remove_from_notes_branch(project_root=exporting_repository.project_root)

    checkout = exporting_repository.clone_notes_branch(tmp_path / "notes")
    assert (
        list(
            (checkout / ProjectLocation.PLANS).glob(f"*/{PlanDocument.MANIFEST.value}")
        )
        == []
    )
    assert [
        path.relative_to(checkout / ProjectLocation.PULL_REQUEST_PROGRESS).as_posix()
        for path in (checkout / ProjectLocation.PULL_REQUEST_PROGRESS).rglob("*")
        if path.is_file()
    ] == [PlanHandover.progress_note_path(UNRELATED_BRANCH).as_posix()]


def test_a_plan_another_plan_still_depends_on_is_not_removed(
    exporting_repository: ScratchRepository,
    dataset_handover: PlanHandover,
    tmp_path: Path,
):
    """
    The plan staying on the notes branch would name an item that no longer exists, so
    the removal is refused, naming its item, and nothing is removed.
    """
    downstream = plan_named(dataset_handover, HandedOverPlan.DOWNSTREAM)
    upstream_only = PlanHandover.from_notes_branch(
        project_root=exporting_repository.project_root,
        plan_identifiers=[HandedOverPlan.UPSTREAM],
    )

    with pytest.raises(PlanStillNamedError) as refusal:
        upstream_only.remove_from_notes_branch(
            project_root=exporting_repository.project_root
        )

    assert refusal.value.named_by == tuple(
        DependencyReference(item.identifier, plan.identifier).text
        for plan in [downstream]
        for item in plan.manifest.items
        if any(
            DependencyReference.from_text(entry).plan_id == HandedOverPlan.UPSTREAM
            for entry in item.dependencies
        )
    )
    checkout = exporting_repository.clone_notes_branch(tmp_path / "notes")
    assert sorted(
        path.parent.name
        for path in (checkout / ProjectLocation.PLANS).glob(
            f"*/{PlanDocument.MANIFEST.value}"
        )
    ) == sorted(HandedOverPlan)
