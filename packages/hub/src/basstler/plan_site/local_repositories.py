"""
The repositories the locally served plan site publishes: every one the viewer can read
whose notes hold plans, and the hub's.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Any

from pydantic import AliasPath, Field

from basstler.github.client import GitHubWriter
from basstler.github.graphql import GraphQLRequest, GraphQLResponse
from basstler.github.repository import GitHubAddress, Repository
from basstler.github.review_models import PageInfo
from basstler.json_model import ValidatedJSONModel
from basstler.locations import ProjectLocation
from basstler.plan_site.hub import PlanHub
from basstler.plan_site.locations import SiteTemplate
from basstler.shell_configuration import PersonalNotesSetting
from basstler.text_file import TextFile

# %% the listing


class RepositoryListingVariable(StrEnum):
    """
    The variables :attr:`SiteTemplate.REPOSITORIES_WITH_PLANS` declares.
    """

    CURSOR = "cursor"
    PLANS = "plans"


class ListedRepositoryNode(ValidatedJSONModel):
    """
    One repository of the viewer's listing.
    """

    full_name: Annotated[str, Field(alias="nameWithOwner")]
    """
    The repository, as ``owner/name``.
    """

    plans: dict[str, Any] | None
    """
    What its notes branch holds at the plans directory, ``None`` when nothing.
    """


class RepositoryListingPage(ValidatedJSONModel):
    """
    One page of the repositories the viewer can read.
    """

    repositories: Annotated[
        list[ListedRepositoryNode],
        Field(validation_alias=AliasPath("viewer", "repositories", "nodes")),
    ]
    """
    The repositories on this page.
    """

    page_info: Annotated[
        PageInfo,
        Field(validation_alias=AliasPath("viewer", "repositories", "pageInfo")),
    ]
    """
    Whether another page follows, and the cursor to request it with.
    """


@dataclass(frozen=True)
class PlanRepositoryDiscovery:
    """
    Finds the repositories the viewer can read whose notes hold plans.
    """

    github: GitHubWriter
    """
    What sends the GraphQL query, as the viewer.
    """

    notes_branch: str
    """
    The branch repositories keep their notes on.
    """

    def repositories(self) -> list[Repository]:
        """
        :return: Each repository with plans on :attr:`notes_branch`, as GitHub lists
            them.
        """
        return [
            Repository.parse(node.full_name)
            for page in self.pages()
            for node in page.repositories
            if node.plans is not None
        ]

    def pages(self) -> Iterator[RepositoryListingPage]:
        """
        :return: Every page of the viewer's repositories, first page first.
        """
        query = TextFile(SiteTemplate.REPOSITORIES_WITH_PLANS).read()
        plans = f"{self.notes_branch}:{ProjectLocation.PLANS.as_posix()}"
        cursor = None
        while True:
            request = GraphQLRequest(
                query=query,
                variables={
                    RepositoryListingVariable.CURSOR: cursor,
                    RepositoryListingVariable.PLANS: plans,
                },
            )
            answer = GraphQLResponse.from_json(self.github.send(request))
            page = RepositoryListingPage.from_json(answer.result())
            yield page
            if not page.page_info.has_next_page:
                return
            cursor = page.page_info.end_cursor


# %% the selection


@dataclass(frozen=True)
class RepositorySelection:
    """
    Which repositories the locally served site publishes.
    """

    registry: Repository | None = None
    """
    The repository whose notes hold the hub file, ``None`` when there is no hub.
    """

    narrowed_to: tuple[Repository, ...] = ()
    """
    The only repositories to publish, every one when empty.
    """

    remote_root: str = GitHubAddress.WEB.value
    """
    Where repositories are fetched from, as :meth:`Repository.clone_url_under` takes it.
    """

    def hub(self, github: GitHubWriter, site_url: str) -> PlanHub:
        """
        :param github: What lists the viewer's repositories.
        :param site_url: The address the site is served from.
        :return: A hub file publishing the selected repositories on that address.
        """
        registry_hub = (
            PlanHub.from_registry(self.registry, self.remote_root)
            if self.registry is not None
            else None
        )
        notes_branch = (
            registry_hub.notes_branch
            if registry_hub is not None
            else PersonalNotesSetting.BRANCH.default
        )
        listed = [str(repository) for repository in self.narrowed_to]
        if not listed:
            discovery = PlanRepositoryDiscovery(github, notes_branch)
            listed = [str(repository) for repository in discovery.repositories()]
            listed += registry_hub.repositories if registry_hub is not None else []
        return PlanHub(
            registry=str(self.registry) if self.registry is not None else None,
            repositories=list(dict.fromkeys(listed)),
            site_url=site_url,
            notes_branch=notes_branch,
        )
