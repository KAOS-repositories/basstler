"""
A goal page whose steps are items of another repository on the same hub.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from basstler.github.repository import Repository
from basstler.locations import ProjectLocation
from basstler.plan.model import ManifestKey, PlanDocument
from basstler.plan_site.__main__ import HubSite, SiteFile
from basstler.plan_site.hub import PlanHub, SiteAddress
from basstler_testing.constants.site import SiteSampleText
from basstler_testing.manifest_builders import manifest_item, minimal_plan
from basstler_testing.recorded_pull_requests import RecordedPullRequestSource

from .test_hub import publish_notes

HOME = Repository.parse("team/basstler-notes")
"""
The repository whose notes hold the goal and the plan its target is in.
"""

OTHER = Repository.parse("team/project-notes")
"""
The repository whose notes hold the plan the target depends on.
"""

ADDRESS = SiteAddress(SiteSampleText.SITE_URL)
"""
Where the site under test is served from.
"""

GOAL_ID = "pilot-on-team-plans"
"""
The goal under test.
"""


def plan_files(plan_id: str, items: list[dict]) -> dict[Path, str]:
    """
    :param plan_id: The one plan of a notes branch.
    :param items: Its items.
    :return: The plans directory's files holding it.
    """
    plan = minimal_plan(
        **{ManifestKey.IDENTIFIER.key: plan_id, ManifestKey.ITEMS.key: items}
    )
    return {Path(plan_id) / PlanDocument.MANIFEST: yaml.safe_dump(plan)}


def build(tmp_path: Path, goal_targets: list[str], listed: list[Repository]) -> Path:
    """
    :param tmp_path: A directory of the test's own.
    :param goal_targets: The targets of the home repository's goal.
    :param listed: The repositories the hub lists.
    :return: The directory the site was built into.
    """
    remotes = tmp_path / "remotes"
    goal = {
        "id": GOAL_ID,
        "title": "The pilot runs on team plans",
        "targets": goal_targets,
    }
    publish_notes(
        remotes,
        HOME,
        {
            **plan_files(
                "team-repository",
                [
                    manifest_item(
                        "migrate-pilot",
                        branch=None,
                        depends_on=[f"{OTHER}:kpi-collection/kpi-report"],
                    )
                ],
            ),
            Path(ProjectLocation.PLAN_GOALS.name) / f"{GOAL_ID}.yaml": yaml.safe_dump(
                goal
            ),
        },
    )
    publish_notes(
        remotes,
        OTHER,
        plan_files("kpi-collection", [manifest_item("kpi-report", branch=None)]),
    )
    output = tmp_path / "site"
    HubSite(
        address=ADDRESS,
        pull_request_source=RecordedPullRequestSource(),
        hub=PlanHub(
            registry=str(HOME),
            repositories=[str(repository) for repository in listed],
            site_url=SiteSampleText.SITE_URL.value,
        ),
        remote_root=str(remotes),
    ).build(output)
    return output


def goal_page(output: Path) -> str:
    """
    :param output: The directory a site was built into.
    :return: The home repository's goal page.
    """
    relative = ADDRESS.goal_url(HOME, GOAL_ID).removeprefix(ADDRESS.hub_url)
    return (output / relative / SiteFile.PAGE).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "listed", [[HOME, OTHER], [HOME]], ids=["both-listed", "only-home-listed"]
)
def test_a_step_in_another_repository_links_to_its_card_there(
    tmp_path: Path, listed: list[Repository]
):
    page = goal_page(build(tmp_path, ["team-repository/migrate-pilot"], listed))

    assert ADDRESS.item_url(OTHER, "kpi-collection", "kpi-report") in page
    assert ADDRESS.item_url(HOME, "team-repository", "migrate-pilot") in page
    assert f"{OTHER}:kpi-collection/kpi-report" in page


def test_a_target_in_another_repository_is_a_step_of_the_goal(tmp_path: Path):
    page = goal_page(
        build(tmp_path, [f"{OTHER}:kpi-collection/kpi-report"], [HOME, OTHER])
    )

    assert ADDRESS.item_url(OTHER, "kpi-collection", "kpi-report") in page
