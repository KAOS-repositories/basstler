"""
Tests for choosing the repositories the locally served plan site publishes.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from basstler.github.client import GitHubResponse, GitHubWrite, GitHubWriter
from basstler.github.repository import Repository
from basstler.plan_site.hub import PlanHub
from basstler.plan_site.local_repositories import (
    PlanRepositoryDiscovery,
    RepositorySelection,
)
from basstler.shell_configuration import PersonalNotesSetting

from basstler_testing.constants.paths import DatasetLocation
from basstler_testing.constants.site import SiteRepository, SiteSampleText
from .test_hub import publish_notes
from basstler.locations import ProjectLocation
from basstler.plan_site.locations import SiteProjectLocation

PRIVATE_NOTES = Repository("owner", "private-notes")

# %% GitHub answering the repository listing


@dataclass
class PagedAnswers(GitHubWriter):
    """
    Answers each write with the next recorded response.
    """

    answers: Iterator[dict[str, Any]]
    """
    The responses, first first.
    """

    writes: list[GitHubWrite] = field(default_factory=list)
    """
    Every write sent.
    """

    def attempt_send(self, write: GitHubWrite) -> GitHubResponse:
        self.writes.append(write)
        return GitHubResponse(next(self.answers))


@pytest.fixture
def github() -> PagedAnswers:
    """
    :return: A viewer whose repositories come in two pages.
    """
    return PagedAnswers(
        iter(
            [
                json.loads(path.read_text(encoding="utf-8"))
                for path in (
                    DatasetLocation.REPOSITORIES_WITH_PLANS_FIRST_PAGE,
                    DatasetLocation.REPOSITORIES_WITH_PLANS_LAST_PAGE,
                )
            ]
        )
    )


def test_discovery_finds_every_repository_whose_notes_hold_plans(github: PagedAnswers):
    discovery = PlanRepositoryDiscovery(github, PersonalNotesSetting.BRANCH.default)

    assert discovery.repositories() == [SiteRepository.NOTES.value, PRIVATE_NOTES]


def test_discovery_asks_for_the_next_page_by_its_cursor(github: PagedAnswers):
    PlanRepositoryDiscovery(github, PersonalNotesSetting.BRANCH.default).repositories()

    first, second = [write.to_json()["variables"] for write in github.writes]
    assert (first["cursor"], second["cursor"]) == (None, "second-page")
    assert first["plans"] == (
        f"{PersonalNotesSetting.BRANCH.default}:{ProjectLocation.PLANS.as_posix()}"
    )


# %% the selection


@pytest.fixture
def registry_remotes(tmp_path: Path) -> Path:
    """
    :return: A directory standing in for GitHub, whose registry's hub file lists the
        registry and a repository the viewer's listing does not hold.
    """
    remote_root = tmp_path / "remotes"
    hub = PlanHub(
        registry=str(SiteRepository.NOTES.value),
        repositories=[
            str(SiteRepository.NOTES.value),
            str(SiteRepository.MISSING.value),
        ],
        site_url=SiteSampleText.SITE_URL.value,
    )
    publish_notes(
        remote_root,
        SiteRepository.NOTES.value,
        {
            SiteProjectLocation.PLAN_HUB.relative_to(
                ProjectLocation.PLANS
            ): hub.to_text()
        },
    )
    return remote_root


def test_the_selection_is_the_discovered_repositories_and_the_hubs(
    github: PagedAnswers, registry_remotes: Path
):
    selection = RepositorySelection(
        registry=SiteRepository.NOTES.value, remote_root=str(registry_remotes)
    )

    hub = selection.hub(github, SiteSampleText.SITE_URL.value)

    assert hub.repositories == [
        str(SiteRepository.NOTES.value),
        str(PRIVATE_NOTES),
        str(SiteRepository.MISSING.value),
    ]
    assert hub.site_url == SiteSampleText.SITE_URL.value


def test_without_a_registry_the_selection_is_what_is_discovered(github: PagedAnswers):
    hub = RepositorySelection().hub(github, SiteSampleText.SITE_URL.value)

    assert hub.repositories == [str(SiteRepository.NOTES.value), str(PRIVATE_NOTES)]


def test_naming_repositories_narrows_the_site_to_them_without_listing_any():
    github = PagedAnswers(iter([]))

    hub = RepositorySelection(narrowed_to=(PRIVATE_NOTES,)).hub(
        github, SiteSampleText.SITE_URL.value
    )

    assert (hub.repositories, github.writes) == ([str(PRIVATE_NOTES)], [])
