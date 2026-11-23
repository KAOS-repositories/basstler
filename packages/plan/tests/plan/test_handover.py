"""
Tests for basstler.plan.handover and its command: handing plans over from one personal-
notes branch and taking them on in another.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from basstler.plan.dependencies import DependencyReference
from basstler.plan.exceptions import (
    HandoverPlanCycleError,
    PlanOutsideHandoverError,
)
from basstler.plan.handover import HandoverGuide, HandoverPlan, PlanHandover
from basstler.plan.model import (
    ExternalDependency,
    ManifestKey,
    PlanManifest,
)
from basstler.plan.repository_rules import RepositoryRules

from basstler_testing.plan.handover import (
    plan_named,
    RECEIVERS_FORK,
    HandedOverPlan,
)


def left_out_upstream(handover: PlanHandover) -> dict[str, PlanManifest]:
    """
    :param handover: The dataset's handover.
    :return: The upstream plan, left out of a handover of the downstream one.
    """
    return {
        HandedOverPlan.UPSTREAM: plan_named(handover, HandedOverPlan.UPSTREAM).manifest
    }


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


def test_a_plan_detached_from_the_plans_it_depends_on_records_them_as_external(
    dataset_handover: PlanHandover,
):
    """
    Each dependency on a left-out plan moves from ``depends_on`` to
    ``external_dependencies``, and the others stay where they are.
    """
    downstream = plan_named(dataset_handover, HandedOverPlan.DOWNSTREAM)

    left_out = left_out_upstream(dataset_handover)

    detached = downstream.detached_from_plans(left_out)

    assert [
        (item.dependencies, item.external_dependencies)
        for item in detached.manifest.items
    ] == [
        (
            [
                entry
                for entry in item.dependencies
                if DependencyReference.from_text(entry).plan_id
                != HandedOverPlan.UPSTREAM
            ],
            [
                ExternalDependency.from_item(
                    plan=left_out[reference.plan_id],
                    item=left_out[reference.plan_id].item_named(
                        reference.item_identifier
                    ),
                )
                for entry in item.dependencies
                for reference in [DependencyReference.from_text(entry)]
                if reference.plan_id == HandedOverPlan.UPSTREAM
            ],
        )
        for item in downstream.manifest.items
    ]
    assert any(item.external_dependencies for item in detached.manifest.items)


def test_a_detached_plan_is_handed_over_without_the_plans_it_depended_on(
    dataset_handover: PlanHandover,
):
    """
    With its dependencies recorded as external, nothing in the plan names a left-out
    plan any more, so it is handed over alone.
    """
    detached = plan_named(
        dataset_handover, HandedOverPlan.DOWNSTREAM
    ).detached_from_plans(left_out_upstream(dataset_handover))

    handover = PlanHandover(
        plans=(detached,), progress_notes={}, repository_rules=RepositoryRules()
    )

    assert handover.plans == (detached,)


def test_a_guide_names_the_external_dependencies_of_an_item(
    dataset_handover: PlanHandover,
):
    """
    The receiver reads which work an item stacked on that was not handed over, what it
    was, and what to do with it.
    """
    detached = plan_named(
        dataset_handover, HandedOverPlan.DOWNSTREAM
    ).detached_from_plans(left_out_upstream(dataset_handover))
    handover = PlanHandover(
        plans=(detached,), progress_notes={}, repository_rules=RepositoryRules()
    )

    guide = HandoverGuide(handover=handover).render()

    external = [
        entry
        for item in detached.manifest.items
        for entry in item.external_dependencies
    ]
    assert external
    assert ExternalDependency.guidance in guide
    assert all(
        text in guide
        for entry in external
        for text in (
            entry.reference,
            entry.title,
            entry.plan_description,
            entry.notes or entry.title,
        )
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


# %% importing


# %% removing handed-over plans


# %% moving onto the receiver's repository


def test_a_plan_moved_to_another_repository_keeps_its_started_items_where_their_work_is(
    dataset_handover: PlanHandover,
):
    """
    Started items stay on their repository, the others follow the new default, and the
    tracking issue, a number on the old default, is dropped; an import first reopens the
    underway items' pull requests on the receiver's repository.
    """
    upstream = plan_named(dataset_handover, HandedOverPlan.UPSTREAM)

    moved = upstream.moved_to_repository(RECEIVERS_FORK).manifest

    assert moved.default_repository == RECEIVERS_FORK
    assert [moved.repository_of(item) for item in moved.items] == [
        upstream.manifest.default_repository
        if item.branch or item.pull_request_number is not None
        else RECEIVERS_FORK
        for item in upstream.manifest.items
    ]
    assert ManifestKey.TRACKING_ISSUE.key not in moved.content


def test_a_plan_already_on_the_receivers_repository_is_not_moved(
    dataset_handover: PlanHandover,
):
    """
    A receiver pushing to the sender's repository takes the plan over unchanged.
    """
    upstream = plan_named(dataset_handover, HandedOverPlan.UPSTREAM)

    assert (
        upstream.moved_to_repository(upstream.manifest.default_repository) == upstream
    )
