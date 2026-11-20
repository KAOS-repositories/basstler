"""
Tests for the plan page's handover button: the plans its command names, and the command
the browser copies with the receiver typed beside it.
"""

from __future__ import annotations

from http import HTTPStatus
from pathlib import Path

from playwright.sync_api import Page, expect

from basstler.plan.dependencies import DependencyReference, PlanDirectory
from basstler.plan.handover_options import PlanHandoverCommand, PlanHandoverOption
from basstler.plan.model import ItemStatus
from basstler.plan.structure import Item, Plan
from basstler.plan_site.__main__ import RepositorySite

from ..fixture_plans import PLAN_UNDER_TEST_ID
from ..github.pull_request_api import api_pull_request
from .first_plan import FIRST_PLAN, OPEN_PULL_REQUEST, PLAN_REPOSITORY
from .plan_page_builders import item, make_renderer
from .test_live_states import answers_with, open_first_plan_page

# %% plans the command names

DEPENDED_ON, DEPENDED_ON_THROUGH_IT, ABSENT = (
    "depended-on-plan",
    "depended-on-through-it-plan",
    "absent-plan",
)
"""
A plan the rendered plan depends on, a plan only that one depends on, and a plan the
directory lacks, which that one also depends on.
"""


def a_plan_depending_on(identifier: str, depended_on: list[str]) -> Plan:
    """
    :param identifier: The plan's id.
    :param depended_on: The plans its one item depends on an item of.
    :return: The plan.
    """
    return Plan(
        id=identifier,
        title=identifier,
        description="desc",
        default_repository="owner/repo",
        waves=[],
        tracks=[],
        items=[a_dependent_item(depended_on)],
    )


def a_dependent_item(depended_on: list[str]) -> Item:
    """
    :param depended_on: The plans the item depends on an item of.
    :return: A not-started item.
    """
    return item(
        "a",
        ItemStatus.NOT_STARTED,
        depends_on=[
            DependencyReference(item_identifier="a", plan_id=plan_id).text
            for plan_id in depended_on
        ],
    )


def test_handover_button_names_the_plan_and_every_plan_it_depends_on(tmp_path: Path):
    """
    An offer names the plan, then every plan it depends on directly or through another,
    even one the directory lacks.
    """
    directory = PlanDirectory(
        tmp_path,
        plans_by_id={
            DEPENDED_ON: a_plan_depending_on(
                DEPENDED_ON, [DEPENDED_ON_THROUGH_IT, ABSENT, PLAN_UNDER_TEST_ID]
            ),
            DEPENDED_ON_THROUGH_IT: a_plan_depending_on(DEPENDED_ON_THROUGH_IT, []),
        },
    )
    renderer = make_renderer(
        [a_dependent_item([DEPENDED_ON])], plan_directory=directory
    )

    button = renderer.render().handover_button

    assert button.plan_identifiers == (
        PLAN_UNDER_TEST_ID,
        *sorted([DEPENDED_ON, DEPENDED_ON_THROUGH_IT, ABSENT]),
    )


def test_handover_button_names_only_the_plan_when_it_depends_on_no_other():
    """
    A plan depending on no other plan is offered alone.
    """
    renderer = make_renderer([item("a", ItemStatus.NOT_STARTED)])

    button = renderer.render().handover_button

    assert button.plan_identifiers == (PLAN_UNDER_TEST_ID,)


# %% the command the browser copies

RECEIVER_LOGIN = "alice"
"""
The receiver typed beside the button.
"""

CLIPBOARD_RECORDER = Path(__file__).with_name("clipboard_recorder.js")
"""
Replaces the browser's clipboard with a list of what was copied.
"""


def copy_with_receiver(page: Page, output: Path, receiver: str) -> list[str]:
    """
    Open the first plan's page, type *receiver* beside the handover button and click it.

    :return: What the page copied.
    """
    page.add_init_script(path=CLIPBOARD_RECORDER)
    open_first_plan_page(
        page, output, answers_with((HTTPStatus.OK, api_pull_request(OPEN_PULL_REQUEST)))
    )
    page.locator(".handover-receiver").fill(receiver)
    page.locator(".handover-group .action-button").click()
    return page.evaluate("window.copiedTexts")


def expected_command(receiver_repository: str) -> str:
    """
    :param receiver_repository: The receiver's repository as ``owner/name``.
    :return: The offer of the first plan to :data:`RECEIVER_LOGIN`.
    """
    return " ".join(
        [
            PlanHandoverCommand.OFFER.invocation,
            FIRST_PLAN.id,
            PlanHandoverOption.RECEIVER_REPOSITORY,
            receiver_repository,
            PlanHandoverOption.RECEIVER_LOGIN,
            RECEIVER_LOGIN,
        ]
    )


def test_a_login_copies_the_offer_to_their_fork_of_the_plan_repository(
    site: RepositorySite, browser_page: Page, tmp_path: Path
):
    """
    A login stands for the receiver's fork, named like the plan's repository.
    """
    site.build(tmp_path)

    copied = copy_with_receiver(browser_page, tmp_path, RECEIVER_LOGIN)

    assert copied == [expected_command(f"{RECEIVER_LOGIN}/{PLAN_REPOSITORY.name}")]


def test_a_repository_copies_the_offer_to_that_repository(
    site: RepositorySite, browser_page: Page, tmp_path: Path
):
    """
    An ``owner/name`` receiver is offered on that repository.
    """
    site.build(tmp_path)
    repository = f"{RECEIVER_LOGIN}/renamed-fork"

    copied = copy_with_receiver(browser_page, tmp_path, repository)

    assert copied == [expected_command(repository)]


def test_a_receiver_that_is_no_login_copies_nothing(
    site: RepositorySite, browser_page: Page, tmp_path: Path
):
    """
    A receiver that is neither a login nor a repository is marked and nothing is copied.
    """
    site.build(tmp_path)

    copied = copy_with_receiver(browser_page, tmp_path, "alice; rm -rf ~")

    assert copied == []
    expect(browser_page.locator(".handover-receiver")).to_have_class(
        "handover-receiver handover-receiver-invalid"
    )
