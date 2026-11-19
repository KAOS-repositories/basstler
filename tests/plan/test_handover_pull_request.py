"""
Tests for basstler.plan.handover_pull_request: offering a plan handover as a pull
request on the receiver's repository, and taking it over from there.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from basstler.github.client import GitHubClient, GitHubResponse, GitHubWrite
from basstler.github.issue import IssueClosing, IssueComment
from basstler.github.pull_request import NewPullRequest, PullRequestDescription
from basstler.github.repository import Repository, RepositoryBranch
from basstler.plan.exceptions import HandoverPullRequestNotChosenError
from basstler.plan.handover import PlanHandover
from basstler.plan.handover_pull_request import (
    HandoverOffer,
    HandoverPullRequestDescription,
    HandoverPullRequests,
)
from basstler.plan.model import PlanDocument, PlanManifest

from ..scratch_repository import ScratchRepository
from .conftest import RECEIVERS_FORK, HandedOverPlan

# %% a stand-in for GitHub


@dataclass
class PullRequestHostingClient(GitHubClient):
    """
    Hosts the pull requests of one repository: opening one keeps its head commit under
    ``refs/pull/<number>/head`` of that repository's bare remote, as GitHub does.
    """

    sender: ScratchRepository
    """
    The clone the opened pull requests' heads are pushed from.
    """

    host: ScratchRepository
    """
    The clone of the repository the pull requests are opened on.
    """

    pull_requests: list[dict[str, Any]] = field(default_factory=list)
    """
    Every pull request opened, as REST describes it.
    """

    sent: list[GitHubWrite] = field(default_factory=list)
    """
    Every write sent, oldest first.
    """

    def get(self, path: str) -> Any:
        pytest.fail(f"read {path}, which a handover pull request never needs")

    def get_pages(self, path: str) -> list[Any]:
        return [
            pull_request
            for pull_request in self.pull_requests
            if pull_request["state"] == "open"
        ]

    def attempt_send(self, write: GitHubWrite) -> GitHubResponse:
        self.sent.append(write)
        if isinstance(write, NewPullRequest):
            return GitHubResponse(self.open(write))
        numbered = {
            pull_request["number"]: pull_request for pull_request in self.pull_requests
        }
        if isinstance(write, PullRequestDescription):
            numbered[write.number]["body"] = write.body
        if isinstance(write, IssueClosing):
            numbered[write.number]["state"] = "closed"
        return GitHubResponse(None)

    def open(self, opening: NewPullRequest) -> dict[str, Any]:
        """
        :param opening: The pull request to open.
        :return: It, as REST describes it.
        """
        number = len(self.pull_requests) + 1
        commit = self.sender.git.run(
            "ls-remote", "origin", f"refs/heads/{opening.head.name}"
        ).split()[0]
        self.sender.run_git(
            "push",
            "--quiet",
            str(self.host.work_remote_path),
            f"{commit}:refs/pull/{number}/head",
        )
        pull_request = {
            "number": number,
            "node_id": f"PR_{number}",
            "html_url": opening.base.repository.pull_request_url(number),
            "state": "open",
            "body": opening.body,
            "base": {"sha": commit, "ref": opening.base.name},
            "head": {"sha": commit, "ref": opening.head.name},
        }
        self.pull_requests.append(pull_request)
        return pull_request


# %% the scenario


@pytest.fixture
def sender_reaching_the_receiver(
    exporting_repository: ScratchRepository, receivers_fork: ScratchRepository
) -> ScratchRepository:
    """
    :return: The sender's clone, resolving the receiver's fork to the receiver's remote.
    """
    exporting_repository.run_git(
        "config",
        exporting_repository.url_rewriting_key(str(receivers_fork.work_remote_path)),
        RECEIVERS_FORK.clone_url,
    )
    return exporting_repository


def offer_to_receiver(
    sender: ScratchRepository, client: PullRequestHostingClient
) -> HandoverOffer:
    """
    Offer the dataset's plans from the sender's notes branch to the receiver's fork.

    :param sender: The sender's clone.
    :param client: Hosts the receiver's pull requests.
    :return: The offer made.
    """
    offer = HandoverOffer(
        handover=PlanHandover.from_notes_branch(
            project_root=sender.project_root,
            plan_identifiers=list(HandedOverPlan),
        ),
        base=RepositoryBranch(repository=RECEIVERS_FORK, name="main"),
        receiver=RECEIVERS_FORK.owner,
        git=sender.git,
    )
    offer.offer(client=client)
    return offer


@pytest.fixture
def hosting_client(
    sender_reaching_the_receiver: ScratchRepository, receivers_fork: ScratchRepository
) -> PullRequestHostingClient:
    """
    :return: GitHub, hosting the receiver's fork's pull requests.
    """
    return PullRequestHostingClient(
        sender=sender_reaching_the_receiver, host=receivers_fork
    )


# %% offering


def test_an_offer_opens_one_draft_pull_request_marked_as_a_handover(
    sender_reaching_the_receiver: ScratchRepository,
    hosting_client: PullRequestHostingClient,
):
    """
    The pull request is a draft, so it cannot be merged by accident, and its description
    carries the marker an import finds it by.
    """
    offer_to_receiver(sender_reaching_the_receiver, hosting_client)

    (opening,) = hosting_client.sent
    assert isinstance(opening, NewPullRequest)
    assert opening.draft
    assert HandoverPullRequestDescription.marker in opening.body


def test_offering_the_same_plans_again_updates_the_open_pull_request(
    sender_reaching_the_receiver: ScratchRepository,
    hosting_client: PullRequestHostingClient,
):
    """
    A second offer of the same plans pushes to the same branch and rewrites the open
    pull request's description instead of opening another.
    """
    offer_to_receiver(sender_reaching_the_receiver, hosting_client)
    offer_to_receiver(sender_reaching_the_receiver, hosting_client)

    assert [type(write) for write in hosting_client.sent] == [
        NewPullRequest,
        PullRequestDescription,
    ]


def test_the_offered_commit_stands_on_the_receivers_branch(
    sender_reaching_the_receiver: ScratchRepository,
    receivers_fork: ScratchRepository,
    hosting_client: PullRequestHostingClient,
):
    """
    The pull request's head is one commit on top of the base, so it shows only the
    handover's files.
    """
    offer_to_receiver(sender_reaching_the_receiver, hosting_client)

    head = receivers_fork.git.run(
        "ls-remote", str(receivers_fork.work_remote_path), "refs/pull/1/head"
    ).split()[0]
    base = receivers_fork.git.run(
        "ls-remote", str(receivers_fork.work_remote_path), "refs/heads/main"
    ).split()[0]
    receivers_fork.run_git("fetch", "--quiet", "origin", "refs/pull/1/head")
    assert receivers_fork.git.parents_of(head) == (base,)


# %% taking it over


def test_a_handover_is_taken_over_from_its_pull_request_onto_the_receivers_fork(
    sender_reaching_the_receiver: ScratchRepository,
    receivers_fork: ScratchRepository,
    hosting_client: PullRequestHostingClient,
    tmp_path: Path,
):
    """
    The receiver's notes branch holds every plan rehomed onto their fork, and the pull
    request is answered and closed.
    """
    offered = offer_to_receiver(sender_reaching_the_receiver, hosting_client)

    HandoverPullRequests(git=receivers_fork.git).take_over(
        client=hosting_client,
        requested_number=None,
        project_root=receivers_fork.project_root,
    )

    checkout = receivers_fork.clone_notes_branch(tmp_path / "receiver-notes")
    assert {
        plan.identifier: PlanManifest.from_file(
            checkout / PlanDocument.MANIFEST.path_within_notes_branch(plan.identifier)
        ).content
        for plan in offered.handover.plans
    } == {
        plan.identifier: plan.rehomed(RECEIVERS_FORK).manifest.content
        for plan in offered.handover.plans
    }
    assert [type(write) for write in hosting_client.sent[1:]] == [
        IssueComment,
        IssueClosing,
    ]
    assert [pull_request["state"] for pull_request in hosting_client.pull_requests] == [
        "closed"
    ]


def test_an_import_with_no_handover_pull_request_open_names_none(
    receivers_fork: ScratchRepository,
    hosting_client: PullRequestHostingClient,
):
    """
    With nothing offered, the import says so rather than saving nothing silently.
    """
    with pytest.raises(HandoverPullRequestNotChosenError) as refusal:
        HandoverPullRequests(git=receivers_fork.git).take_over(
            client=hosting_client,
            requested_number=None,
            project_root=receivers_fork.project_root,
        )

    assert refusal.value.offered_numbers == ()


def test_an_import_of_a_pull_request_not_offered_is_refused(
    sender_reaching_the_receiver: ScratchRepository,
    receivers_fork: ScratchRepository,
    hosting_client: PullRequestHostingClient,
):
    """
    A number that names no open handover pull request is refused, naming the ones that
    are open.
    """
    offer_to_receiver(sender_reaching_the_receiver, hosting_client)
    (offered,) = hosting_client.pull_requests

    with pytest.raises(HandoverPullRequestNotChosenError) as refusal:
        HandoverPullRequests(git=receivers_fork.git).take_over(
            client=hosting_client,
            requested_number=offered["number"] + 1,
            project_root=receivers_fork.project_root,
        )

    assert refusal.value.offered_numbers == (offered["number"],)


def test_the_receivers_repository_is_the_one_its_origin_configures(
    receivers_fork: ScratchRepository,
):
    """
    The pull requests are looked for on the repository ``origin`` names, not on git's
    rewrite of its URL.
    """
    assert (
        HandoverPullRequests(git=receivers_fork.git).repository
        == Repository.from_configured_remote(receivers_fork.git)
        == RECEIVERS_FORK
    )
