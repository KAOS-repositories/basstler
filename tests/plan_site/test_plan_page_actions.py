"""
Tests for :mod:`basstler.plan_site.plan_page`: which action button each item gets, and
how the page renders it.
"""

from __future__ import annotations

import pytest

from basstler.github.pull_request_state import (
    LivePullRequests,
    PullRequestRecord,
    PullRequestState,
)
from basstler.plan.model import ItemStatus
from basstler.plan.model_alias import ModelAlias
from basstler.plan.structure import Plan, Track, Wave
from basstler.plan_site.plan_page import PlanPage

from ..fixture_plans import (
    PLAN_UNDER_TEST_ID,
)
from .plan_page_builders import (
    STYLESHEET_URL,
    item,
    make_renderer,
)

# %% the action each item gets


def test_action_is_start_now_for_a_not_started_item():
    """
    A not-started item with nothing to wait on gets the kickoff command.
    """
    renderer = make_renderer([item("a", ItemStatus.NOT_STARTED)])
    page = renderer.render()
    action = page.cards_by_identifier["a"].action
    assert action.label == "Start now"
    assert action.command == "/plan-item-kickoff test-plan a"


def test_action_none_for_a_not_started_item_while_a_dependency_is_not_ready():
    """
    A not-started item gets no button while a dependency is not ready.
    """
    items = [
        item("a", ItemStatus.NOT_STARTED),
        item("b", ItemStatus.NOT_STARTED, depends_on=["a"]),
    ]
    renderer = make_renderer(items)
    page = renderer.render()
    assert page.cards_by_identifier["b"].action is None


def test_action_set_once_every_dependency_is_ready():
    """
    A not-started item gets the kickoff command once every dependency is done.
    """
    items = [
        item("a", ItemStatus.DONE),
        item("b", ItemStatus.NOT_STARTED, depends_on=["a"]),
    ]
    renderer = make_renderer(items)
    page = renderer.render()
    assert (
        page.cards_by_identifier["b"].action.command == "/plan-item-kickoff test-plan b"
    )


def test_action_set_when_dependency_is_open_and_ready_for_review():
    """
    A dependency whose pull request is ready for review lets its dependent start.
    """
    pull_requests_by_repository = {
        "owner/repo": {"1": PullRequestRecord(state=PullRequestState.OPEN, draft=False)}
    }
    items = [
        item("a", ItemStatus.IN_PROGRESS, pull_request_number=1),
        item("b", ItemStatus.NOT_STARTED, depends_on=["a"]),
    ]
    renderer = make_renderer(
        items, pull_requests_by_repository=pull_requests_by_repository
    )
    page = renderer.render()
    assert page.cards_by_identifier["b"].action is not None


def test_action_none_for_a_not_started_item_when_dependency_is_still_a_draft():
    """
    A dependency whose pull request is a draft holds its dependent's button back.
    """
    pull_requests_by_repository = {
        "owner/repo": {"1": PullRequestRecord(state=PullRequestState.OPEN, draft=True)}
    }
    items = [
        item("a", ItemStatus.IN_PROGRESS, pull_request_number=1),
        item("b", ItemStatus.NOT_STARTED, depends_on=["a"]),
    ]
    renderer = make_renderer(
        items, pull_requests_by_repository=pull_requests_by_repository
    )
    page = renderer.render()
    assert page.cards_by_identifier["b"].action is None


def test_action_ready_check_is_order_independent():
    """
    A dependency listed after its dependent still counts as ready.
    """
    # "b" depends on "a", but "a" appears later in plan.items - the
    # dependency's live_state must still be classified before "b"'s
    # action is computed.
    items = [
        item("b", ItemStatus.NOT_STARTED, depends_on=["a"]),
        item("a", ItemStatus.DONE),
    ]
    renderer = make_renderer(items)
    page = renderer.render()
    assert (
        page.cards_by_identifier["b"].action.command == "/plan-item-kickoff test-plan b"
    )


def test_action_none_for_a_done_item():
    """
    A done item gets no button.
    """
    renderer = make_renderer([item("a", ItemStatus.DONE)])
    page = renderer.render()
    assert page.cards_by_identifier["a"].action is None


def test_action_is_resolve_for_a_blocked_item():
    """
    A blocked item gets the resolve command, labelled Resolve.
    """
    renderer = make_renderer([item("a", ItemStatus.BLOCKED)])
    page = renderer.render()
    action = page.cards_by_identifier["a"].action
    assert action.label == "Resolve"
    assert action.command == "/plan-item-resolve test-plan a"


def test_action_is_resume_for_an_in_progress_item():
    """
    An in-progress item gets the resolve command, labelled Resume.
    """
    renderer = make_renderer([item("a", ItemStatus.IN_PROGRESS)])
    page = renderer.render()
    action = page.cards_by_identifier["a"].action
    assert action.label == "Resume"
    assert action.command == "/plan-item-resolve test-plan a"


def test_action_is_reconsider_for_a_deferred_item():
    """
    A deferred item gets the resolve command, labelled Reconsider.
    """
    renderer = make_renderer([item("a", ItemStatus.DEFERRED)])
    page = renderer.render()
    action = page.cards_by_identifier["a"].action
    assert action.label == "Reconsider"
    assert action.command == "/plan-item-resolve test-plan a"


# %% rendered action buttons


def test_render_shows_start_now_button_for_a_not_started_item():
    plan = Plan(
        id=PLAN_UNDER_TEST_ID,
        title="Test Plan",
        description="desc",
        default_repository="owner/repo",
        waves=[Wave(id="wave-1", name="Wave One")],
        tracks=[Track(id="track-1", name="Track One", wave="wave-1")],
        items=[item("a", ItemStatus.NOT_STARTED)],
    )
    renderer = PlanPage(
        stylesheet_url=STYLESHEET_URL,
        plan=plan,
        roadmap_text="",
        live_pull_requests=LivePullRequests(),
    )
    output = renderer.render().html
    assert 'data-action-command="/plan-item-kickoff test-plan a"' in output
    assert "Start now" in output


def test_render_shows_resolve_resume_reconsider_buttons_for_underway_items():
    plan = Plan(
        id=PLAN_UNDER_TEST_ID,
        title="Test Plan",
        description="desc",
        default_repository="owner/repo",
        waves=[Wave(id="wave-1", name="Wave One")],
        tracks=[Track(id="track-1", name="Track One", wave="wave-1")],
        items=[
            item("a", ItemStatus.IN_PROGRESS),
            item("b", ItemStatus.BLOCKED),
            item("c", ItemStatus.DEFERRED),
        ],
    )
    renderer = PlanPage(
        stylesheet_url=STYLESHEET_URL,
        plan=plan,
        roadmap_text="",
        live_pull_requests=LivePullRequests(),
    )
    output = renderer.render().html
    assert 'data-action-command="/plan-item-resolve test-plan a"' in output
    assert 'data-action-command="/plan-item-resolve test-plan b"' in output
    assert 'data-action-command="/plan-item-resolve test-plan c"' in output
    assert "Resume" in output
    assert "Resolve" in output
    assert "Reconsider" in output


def test_render_omits_action_button_for_a_done_item():
    plan = Plan(
        id=PLAN_UNDER_TEST_ID,
        title="Test Plan",
        description="desc",
        default_repository="owner/repo",
        waves=[Wave(id="wave-1", name="Wave One")],
        tracks=[Track(id="track-1", name="Track One", wave="wave-1")],
        items=[item("a", ItemStatus.DONE)],
    )
    renderer = PlanPage(
        stylesheet_url=STYLESHEET_URL,
        plan=plan,
        roadmap_text="",
        live_pull_requests=LivePullRequests(),
    )
    output = renderer.render().html
    assert 'data-action-command="' not in output


def render_item_page(*items) -> str:
    plan = Plan(
        id=PLAN_UNDER_TEST_ID,
        title="Test Plan",
        description="desc",
        default_repository="owner/repo",
        waves=[Wave(id="wave-1", name="Wave One")],
        tracks=[Track(id="track-1", name="Track One", wave="wave-1")],
        items=list(items),
    )
    return (
        PlanPage(
            stylesheet_url=STYLESHEET_URL,
            plan=plan,
            roadmap_text="",
            live_pull_requests=LivePullRequests(),
        )
        .render()
        .html
    )


def test_render_offers_every_model_alias_and_no_session_default_in_the_dropdown():
    output = render_item_page(item("a", ItemStatus.NOT_STARTED))
    for alias in ModelAlias:
        assert f'data-value="{alias.value}"' in output
        assert f">{alias.label}</li>" in output
    assert 'data-value=""' not in output
    assert 'class="model-picker-toggle"' in output
    assert 'class="model-select"' not in output


@pytest.mark.parametrize("status", [ItemStatus.NOT_STARTED, ItemStatus.IN_PROGRESS])
def test_render_preselects_the_items_recommended_model_on_its_action_button(status):
    alias = ModelAlias.OPUS
    output = render_item_page(item("a", status, recommended_model=alias))
    assert f'<span class="model-picker" data-model="{alias.value}"' in output
    assert f"{alias.label} ▾</button>" in output
    assert (
        f'data-value="{alias.value}" onclick="planPageSelectModel(event, this)"'
        ' class="model-picker-option-selected"'
    ) in output


def test_render_preselects_no_model_for_an_item_with_no_recommendation():
    output = render_item_page(item("a", ItemStatus.NOT_STARTED))
    assert '<span class="model-picker" data-model=""' in output
    assert ' class="model-picker-option-selected"' not in output
