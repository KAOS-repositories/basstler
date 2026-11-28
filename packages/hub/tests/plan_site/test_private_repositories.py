"""
Tests that the public site build never publishes a repository not known to be public,
while the local build publishes it in full.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from basstler.github.repository_visibility import RepositoryVisibilityReader
from basstler.plan.structure import Plan
from basstler.plan_site.__main__ import HubSite, PlanSource, SiteFile
from basstler.plan_site.hub import PlanHub, SiteAddress
from basstler.plan_site.hub_page import RepositorySummary, SiteSummary
from basstler.plan_site.publication_scope import (
    EveryRepository,
    PublicationScope,
    PublicRepositoriesOnly,
)

from basstler_testing.constants.paths import DatasetLocation
from basstler_testing.constants.site import SiteRepository, SiteSampleText
from basstler_testing.github.visibility_client import visibility_client
from basstler_testing.recorded_pull_requests import RecordedPullRequestSource
from .test_hub import publish_notes

# %% a hub listing a public and a private repository


@pytest.fixture
def private_plan() -> Plan:
    """
    The one plan the private repository's notes hold.
    """
    [source] = PlanSource.every_plan_in(DatasetLocation.SITE_PRIVATE_PLANS.value)
    return Plan.from_mapping(source.manifest)


@pytest.fixture
def remotes(tmp_path: Path) -> Path:
    """
    A directory standing in for GitHub: the public notes repository carries the
    dataset's plans, the private one :func:`private_plan`.
    """
    remote_root = tmp_path / "remotes"
    for repository, plans_directory in (
        (SiteRepository.NOTES.value, DatasetLocation.SITE_PLANS.value),
        (SiteRepository.PRIVATE.value, DatasetLocation.SITE_PRIVATE_PLANS.value),
    ):
        publish_notes(
            remote_root,
            repository,
            {
                path.relative_to(plans_directory): path.read_text(encoding="utf-8")
                for path in plans_directory.rglob("*")
                if path.is_file()
            },
        )
    return remote_root


def build(scope: PublicationScope, remotes: Path, output: Path) -> SiteSummary:
    """
    :param scope: Which listed repositories the build may publish.
    :param remotes: Where the listed repositories are fetched from.
    :param output: The directory to write the site into.
    :return: The site's summary.
    """
    listed = (SiteRepository.NOTES.value, SiteRepository.PRIVATE.value)
    return HubSite(
        address=SiteAddress(SiteSampleText.SITE_URL),
        pull_request_source=RecordedPullRequestSource(),
        hub=PlanHub(
            registry=str(SiteRepository.NOTES.value),
            repositories=[str(repository) for repository in listed],
        ),
        publication_scope=scope,
        remote_root=str(remotes),
    ).build(output)


def files_holding(text: str, site: Path) -> list[Path]:
    """
    :param text: The text to look for.
    :param site: The built site.
    :return: Every built file holding it, the site digest included.
    """
    return [
        path.relative_to(site)
        for path in site.rglob("*")
        if path.is_file() and text.encode() in path.read_bytes()
    ]


PUBLIC_ONLY = PublicRepositoriesOnly(
    RepositoryVisibilityReader(
        visibility_client(
            public=[SiteRepository.NOTES.value], private=[SiteRepository.PRIVATE.value]
        )
    )
)
"""
The public build's scope, over GitHub saying the notes repository is public and the
other private.
"""

VISIBILITY_UNKNOWN = PublicRepositoriesOnly(
    RepositoryVisibilityReader(visibility_client(public=[SiteRepository.NOTES.value]))
)
"""
The public build's scope, over GitHub refusing to describe the private repository.
"""


# %% the public build


@pytest.mark.parametrize("scope", [PUBLIC_ONLY, VISIBILITY_UNKNOWN])
def test_the_public_build_writes_a_private_plan_into_no_file(
    scope: PublicationScope, private_plan: Plan, remotes: Path, tmp_path: Path
):
    site = tmp_path / "site"
    build(scope, remotes, site)
    assert files_holding(private_plan.title, site) == []
    assert not (site / str(SiteRepository.PRIVATE.value)).exists()


@pytest.mark.parametrize("scope", [PUBLIC_ONLY, VISIBILITY_UNKNOWN])
def test_the_public_build_shows_a_private_repository_as_left_out(
    scope: PublicationScope, remotes: Path, tmp_path: Path
):
    summary = build(scope, remotes, tmp_path / "site")
    private = SiteRepository.PRIVATE.value
    assert summary.repositories[1] == RepositorySummary.left_out(
        str(private), scope.exclusion_of(private)
    )


def test_the_public_build_counts_only_the_public_repository(
    remotes: Path, tmp_path: Path
):
    summary = build(PUBLIC_ONLY, remotes, tmp_path / "site")
    public, _ = summary.repositories
    assert summary.total == public.total


def test_the_public_build_publishes_a_public_repository(remotes: Path, tmp_path: Path):
    summary = build(PUBLIC_ONLY, remotes, tmp_path / "site")
    assert summary.repositories[0].left_out_reason is None


# %% the local build


def test_the_local_build_publishes_a_private_plan(
    private_plan: Plan, remotes: Path, tmp_path: Path
):
    site = tmp_path / "site"
    build(EveryRepository(), remotes, site)
    private_page = Path(str(SiteRepository.PRIVATE.value), private_plan.id)
    assert private_page / SiteFile.PAGE in files_holding(private_plan.title, site)
