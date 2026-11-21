"""
Tests for basstler.plan.handover_pull_request: offering a plan handover as a pull
request on the receiver's repository, and taking it over from there.
"""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from basstler.git.commands import GitCommandRunner
from basstler.github.client import GitHubClient, GitHubResponse, GitHubWrite
from basstler.github.issue import IssueClosing, IssueComment
from basstler.github.pull_request import NewPullRequest, PullRequestDescription
from basstler.github.repository import Repository, RepositoryBranch
from basstler.github.repository_access import ListingParameter
from basstler.plan.exceptions import HandoverPullRequestNotChosenError
from basstler.plan.dependencies import DependencyReference
from basstler.plan.handover import HandoverPlan, PlanHandover
from basstler.plan.handover_continuation import ContinuedHandover, HandoverImport
from basstler.plan.handover_originals import SenderOriginalPullRequests
from basstler.plan.handover_pull_request import (
    HandoverOffer,
    HandoverPullRequestDescription,
    HandoverPullRequests,
)
from basstler.plan.model import ManifestKey, PlanDocument, PlanItem, PlanManifest
from basstler.plan.repository_rules import RepositoryRules

from ..scratch_repository import ScratchRepository
from .conftest import (
    RECEIVERS_FORK,
    HandedOverPlan,
    plans_repository as sender_repository,
)

# %% a stand-in for GitHub


@dataclass
class PullRequestHostingClient(GitHubClient):
    """
    Serves the sender's pull requests and hosts the receiver's: opening one keeps its
    head commit under ``refs/pull/<number>/head`` of the receiver's bare remote, as
    GitHub does.
    """

    sender: ScratchRepository
    """
    The sender's clone, whose bare remote holds the sender's repository's branches.
    """

    host: ScratchRepository
    """
    The receiver's clone, whose bare remote holds the receiver's repository's branches.
    """

    sender_pull_requests: dict[str, dict[str, Any]] = field(default_factory=dict)
    """
    The sender's pull requests as REST describes them, by their REST path.
    """

    pull_requests: list[dict[str, Any]] = field(default_factory=list)
    """
    Every pull request opened on the receiver's repository, as REST describes it.
    """

    sent: list[GitHubWrite] = field(default_factory=list)
    """
    Every write sent, oldest first.
    """

    def get(self, path: str) -> Any:
        return self.sender_pull_requests[path]

    def get_pages(self, path: str) -> list[Any]:
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(path).query)
        heads = query.get(ListingParameter.HEAD.value)
        return [
            pull_request
            for pull_request in self.pull_requests
            if pull_request["state"] == "open"
            and (
                heads is None
                or f"{pull_request['head']['user']['login']}:"
                f"{pull_request['head']['ref']}"
                in heads
            )
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
        if isinstance(write, IssueClosing) and write.repository == RECEIVERS_FORK:
            numbered[write.number]["state"] = "closed"
        if isinstance(write, IssueClosing) and write.repository != RECEIVERS_FORK:
            self.sender_pull_requests[write.repository.pull_request_path(write.number)][
                "state"
            ] = "closed"
        return GitHubResponse(None)

    def bare_remote_of(self, repository: Repository) -> GitCommandRunner:
        """
        :param repository: The sender's or the receiver's repository.
        :return: The bare repository standing in for it.
        """
        clone = self.host if repository == RECEIVERS_FORK else self.sender
        return GitCommandRunner(clone.work_remote_path)

    def open(self, opening: NewPullRequest) -> dict[str, Any]:
        """
        :param opening: The pull request to open.
        :return: It, as REST describes it.
        """
        number = len(self.pull_requests) + 1
        head_remote = self.bare_remote_of(opening.head.repository)
        commit = head_remote.commit_at(f"refs/heads/{opening.head.name}")
        head_remote.run(
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
            "head": {
                "sha": commit,
                "ref": opening.head.name,
                "user": {"login": opening.head.repository.owner},
            },
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
    sender: ScratchRepository,
    client: PullRequestHostingClient,
    *,
    closes_pull_requests: bool = False,
    plan_identifiers: tuple[HandedOverPlan, ...] = tuple(HandedOverPlan),
) -> HandoverOffer:
    """
    Offer plans of the dataset from the sender's notes branch to the receiver's fork.

    :param sender: The sender's clone.
    :param client: Hosts the receiver's pull requests.
    :param closes_pull_requests: Whether the sender's underway pull requests are closed.
    :param plan_identifiers: The plans offered.
    :return: The offer made.
    """
    offer = HandoverOffer(
        handover=PlanHandover.from_notes_branch(
            project_root=sender.project_root,
            plan_identifiers=list(plan_identifiers),
        ),
        base=RepositoryBranch(repository=RECEIVERS_FORK, name="main"),
        receiver_login=RECEIVERS_FORK.owner,
        git=sender.git,
    )
    offered = offer.push_and_open_pull_request(client=client)
    if closes_pull_requests:
        originals(sender, client, offer.handover).close_open_originals(
            handover_pull_request=offered
        )
    return offer


def originals(
    sender: ScratchRepository, client: PullRequestHostingClient, handover: PlanHandover
) -> SenderOriginalPullRequests:
    """
    :param sender: The sender's clone.
    :param client: Serves the sender's pull requests.
    :param handover: The handover offered.
    :return: The sender's pull requests of its underway items.
    """
    return SenderOriginalPullRequests(
        handover=handover,
        receiver_repository=RECEIVERS_FORK,
        git=sender.git,
        client=client,
    )


def underway_pull_request(
    sender: ScratchRepository, plan: HandoverPlan, item: PlanItem
) -> dict[str, Any]:
    """
    Publish an underway item's branch, one commit on the branch it stacks on, and
    describe its open pull request.

    :param sender: The sender's clone.
    :param plan: The plan holding the item.
    :param item: An item naming a branch and a pull request.
    :return: The pull request as REST describes it.
    """
    (dependency, *_) = item.dependencies or [None]
    base = "main"
    if dependency is not None:
        reference = DependencyReference.from_text(dependency)
        base = next(
            other.branch
            for other_plan in sender_plans(sender)
            if other_plan.identifier == (reference.plan_id or plan.identifier)
            for other in other_plan.manifest.items
            if other.identifier == reference.item_identifier
        )
    sender.run_git("checkout", "--quiet", "-B", item.branch, f"origin/{base}")
    sender.run_git("commit", "--quiet", "--allow-empty", "-m", item.identifier)
    sender.run_git("push", "--quiet", "origin", f"HEAD:refs/heads/{item.branch}")
    sender.run_git("fetch", "--quiet", "origin")
    commit = sender.git.commit_at("HEAD")
    repository = plan.manifest.repository_of(item)
    return {
        "number": item.pull_request_number,
        "html_url": repository.pull_request_url(item.pull_request_number),
        "title": item.content[ManifestKey.TITLE.key],
        "state": "open",
        "merged_at": None,
        "head": {
            "sha": commit,
            "ref": item.branch,
            "user": {"login": repository.owner},
        },
        "base": {"sha": commit, "ref": base},
    }


def sender_plans(sender: ScratchRepository) -> tuple[HandoverPlan, ...]:
    """
    :param sender: The sender's clone.
    :return: The dataset's plans as the sender hands them over.
    """
    return PlanHandover.from_notes_branch(
        project_root=sender.project_root, plan_identifiers=list(HandedOverPlan)
    ).plans


@pytest.fixture
def hosting_client(
    sender_reaching_the_receiver: ScratchRepository, receivers_fork: ScratchRepository
) -> PullRequestHostingClient:
    """
    :return: GitHub, serving the sender's underway pull requests, in dependency order
        so a stacked branch is published after the one it stacks on, and hosting the
        receiver's.
    """
    sender = sender_reaching_the_receiver
    sender.run_git("fetch", "--quiet", "origin")
    receivers_fork.run_git(
        "config",
        receivers_fork.url_rewriting_key(str(sender.work_remote_path)),
        sender_repository().clone_url,
    )
    sender_pull_requests = {}
    for plan in PlanHandover(
        plans=sender_plans(sender),
        progress_notes={},
        repository_rules=RepositoryRules(),
    ).plans_in_saving_order:
        for item in plan.manifest.items:
            if item.branch and item.pull_request_number is not None:
                sender_pull_requests[
                    plan.manifest.repository_of(item).pull_request_path(
                        item.pull_request_number
                    )
                ] = underway_pull_request(sender, plan, item)
    return PullRequestHostingClient(
        sender=sender, host=receivers_fork, sender_pull_requests=sender_pull_requests
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


def take_over(
    receiver: ScratchRepository,
    client: PullRequestHostingClient,
    *,
    continues_underway_work: bool = True,
    requested_number: int | None = None,
) -> ContinuedHandover:
    """
    :param receiver: The receiver's clone.
    :param client: GitHub, hosting the receiver's pull requests.
    :param continues_underway_work: Whether underway items are continued on the fork.
    :param requested_number: The handover pull request asked for.
    :return: The handover as taken over.
    """
    (continued,) = HandoverPullRequests(git=receiver.git).import_and_close(
        importing=HandoverImport(
            project_root=receiver.project_root,
            client=client,
            continues_underway_work=continues_underway_work,
        ),
        requested_number=requested_number,
    )
    return continued


def saved_manifests(
    receiver: ScratchRepository, plans: tuple[HandoverPlan, ...], tmp_path: Path
) -> dict[str, dict[str, Any]]:
    """
    :param receiver: The receiver's clone.
    :param plans: The plans taken over.
    :param tmp_path: Where to check the receiver's notes branch out.
    :return: Each plan's manifest as the receiver's notes branch holds it, by id.
    """
    checkout = receiver.clone_notes_branch(tmp_path / "receiver-notes")
    return {
        plan.identifier: PlanManifest.from_file(
            checkout / PlanDocument.MANIFEST.path_within_notes_branch(plan.identifier)
        ).content
        for plan in plans
    }


def test_a_handover_left_underway_is_moved_onto_the_receivers_fork(
    sender_reaching_the_receiver: ScratchRepository,
    receivers_fork: ScratchRepository,
    hosting_client: PullRequestHostingClient,
    tmp_path: Path,
):
    """
    Taken over without continuing its work, every plan moves onto the receiver's fork
    with its underway items still naming the sender's pull requests, and the handover
    pull request is answered and closed.
    """
    offered = offer_to_receiver(sender_reaching_the_receiver, hosting_client)

    take_over(receivers_fork, hosting_client, continues_underway_work=False)

    assert saved_manifests(receivers_fork, offered.handover.plans, tmp_path) == {
        plan.identifier: plan.moved_to_repository(RECEIVERS_FORK).manifest.content
        for plan in offered.handover.plans
    }
    assert [type(write) for write in hosting_client.sent[1:]] == [
        IssueComment,
        IssueClosing,
    ]
    assert [pull_request["state"] for pull_request in hosting_client.pull_requests] == [
        "closed"
    ]


def test_underway_items_continue_in_pull_requests_on_the_receivers_fork(
    sender_reaching_the_receiver: ScratchRepository,
    receivers_fork: ScratchRepository,
    hosting_client: PullRequestHostingClient,
    tmp_path: Path,
):
    """
    Each underway item's branch is on the receiver's fork at the sender's commit, its
    pull request is opened again there against the same base, and the item names it.
    """
    offered = offer_to_receiver(sender_reaching_the_receiver, hosting_client)

    continued = take_over(receivers_fork, hosting_client)

    receivers_remote = hosting_client.bare_remote_of(RECEIVERS_FORK)
    assert {
        continuation.original.summary.head.name: receivers_remote.commit_at(
            f"refs/heads/{continuation.original.summary.head.name}"
        )
        for continuation in continued.continuations
    } == {
        continuation.original.summary.head.name: continuation.original.summary.head.object_hash
        for continuation in continued.continuations
    }
    reopened = {
        pull_request["number"]: pull_request
        for pull_request in hosting_client.pull_requests
    }
    assert [
        (
            reopened[continuation.continued.number]["head"]["ref"],
            reopened[continuation.continued.number]["base"]["ref"],
        )
        for continuation in continued.continuations
    ] == [
        (
            continuation.original.summary.head.name,
            continuation.original.summary.base.name,
        )
        for continuation in continued.continuations
    ]
    assert saved_manifests(receivers_fork, offered.handover.plans, tmp_path) == {
        plan.identifier: plan.manifest.content for plan in continued.handover.plans
    }
    assert {
        continuation.original.item for continuation in continued.continuations
    } == underway_items(offered.handover)


def test_a_continued_item_names_its_new_pull_request_on_the_receivers_fork(
    sender_reaching_the_receiver: ScratchRepository,
    receivers_fork: ScratchRepository,
    hosting_client: PullRequestHostingClient,
):
    """
    A continued item's pull request is read from the plan's default repository, the
    receiver's fork, under its new number.
    """
    offer_to_receiver(sender_reaching_the_receiver, hosting_client)

    continued = take_over(receivers_fork, hosting_client)

    plans = {plan.identifier: plan for plan in continued.handover.plans}
    assert [
        (
            plans[continuation.original.item.plan_id].manifest.repository_of(item),
            item.pull_request_number,
        )
        for continuation in continued.continuations
        for item in [
            plans[continuation.original.item.plan_id].manifest.item_named(
                continuation.original.item.item_identifier
            )
        ]
    ] == [
        (RECEIVERS_FORK, continuation.continued.number)
        for continuation in continued.continuations
    ]


def test_an_import_with_no_handover_pull_request_open_names_none(
    receivers_fork: ScratchRepository,
    hosting_client: PullRequestHostingClient,
):
    """
    With nothing offered, the import says so rather than saving nothing silently.
    """
    with pytest.raises(HandoverPullRequestNotChosenError) as refusal:
        take_over(receivers_fork, hosting_client)

    assert refusal.value.offered == ()


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
        take_over(
            receivers_fork, hosting_client, requested_number=offered["number"] + 1
        )

    assert [pull_request.number for pull_request in refusal.value.offered] == [
        offered["number"]
    ]


def offer_twice(
    sender: ScratchRepository, client: PullRequestHostingClient
) -> list[int]:
    """
    Offer the upstream plan alone, then every plan, which opens two handover pull
    requests.

    :param sender: The sender's clone.
    :param client: Hosts the receiver's pull requests.
    :return: The numbers of the two pull requests, oldest first.
    """
    offer_to_receiver(sender, client, plan_identifiers=(HandedOverPlan.UPSTREAM,))
    offer_to_receiver(sender, client)
    return [pull_request["number"] for pull_request in client.pull_requests]


def test_several_open_handover_pull_requests_are_named_when_none_is_asked_for(
    sender_reaching_the_receiver: ScratchRepository,
    receivers_fork: ScratchRepository,
    hosting_client: PullRequestHostingClient,
):
    """
    With two handovers open and neither one nor all asked for, the import takes none
    over and names both.
    """
    numbers = offer_twice(sender_reaching_the_receiver, hosting_client)

    with pytest.raises(HandoverPullRequestNotChosenError) as refusal:
        take_over(receivers_fork, hosting_client)

    assert [pull_request.number for pull_request in refusal.value.offered] == numbers
    assert [pull_request["state"] for pull_request in hosting_client.pull_requests] == [
        "open",
        "open",
    ]


def test_every_open_handover_pull_request_is_chosen_when_all_are_asked_for(
    sender_reaching_the_receiver: ScratchRepository,
    receivers_fork: ScratchRepository,
    hosting_client: PullRequestHostingClient,
):
    """
    Asked for all of them, the import takes every open handover over, oldest first.
    """
    numbers = offer_twice(sender_reaching_the_receiver, hosting_client)

    chosen = HandoverPullRequests(
        git=receivers_fork.git
    ).choose_pull_requests_to_take_over(
        client=hosting_client, requested_number=None, takes_every_one=True
    )

    assert [pull_request.number for pull_request in chosen] == numbers


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


# %% the sender's originals


def underway_items(handover: PlanHandover) -> set[DependencyReference]:
    """
    :param handover: A handover of the dataset's plans.
    :return: Every item naming a branch and a pull request.
    """
    return {
        DependencyReference(item_identifier=item.identifier, plan_id=plan.identifier)
        for plan in handover.plans
        for item in plan.manifest.items
        if item.branch and item.pull_request_number is not None
    }


def sender_branches(client: PullRequestHostingClient) -> set[str]:
    """
    :param client: GitHub, serving the sender's pull requests.
    :return: The heads of the sender's underway pull requests still on its repository.
    """
    remote = client.bare_remote_of(sender_repository())
    return {
        pull_request["head"]["ref"]
        for pull_request in client.sender_pull_requests.values()
        if remote.commit_or_none(f"refs/heads/{pull_request['head']['ref']}")
    }


def test_an_offer_closing_pull_requests_closes_every_underway_original(
    sender_reaching_the_receiver: ScratchRepository,
    hosting_client: PullRequestHostingClient,
):
    """
    Each underway item's open pull request on the sender's repository gets a comment
    naming the handover pull request, then is closed.
    """
    offer_to_receiver(
        sender_reaching_the_receiver, hosting_client, closes_pull_requests=True
    )

    (handover_pull_request,) = hosting_client.pull_requests
    comments = [
        write for write in hosting_client.sent if isinstance(write, IssueComment)
    ]
    assert {comment.number for comment in comments} == {
        pull_request["number"]
        for pull_request in hosting_client.sender_pull_requests.values()
    }
    assert all(
        handover_pull_request["html_url"] in comment.body for comment in comments
    )
    assert {
        pull_request["state"]
        for pull_request in hosting_client.sender_pull_requests.values()
    } == {"closed"}


def test_items_whose_originals_were_closed_on_offering_still_continue(
    sender_reaching_the_receiver: ScratchRepository,
    receivers_fork: ScratchRepository,
    hosting_client: PullRequestHostingClient,
):
    """
    A pull request closed unmerged by the handover is continued like an open one.
    """
    offered = offer_to_receiver(
        sender_reaching_the_receiver, hosting_client, closes_pull_requests=True
    )

    continued = take_over(receivers_fork, hosting_client)

    assert {
        continuation.original.item for continuation in continued.continuations
    } == underway_items(offered.handover)


def test_no_original_is_closed_when_the_receiver_works_in_the_senders_repository(
    sender_reaching_the_receiver: ScratchRepository,
    hosting_client: PullRequestHostingClient,
):
    """
    A collaborator continues the items on their existing pull requests, so none of them
    counts as an original to close or delete.
    """
    handover = PlanHandover.from_notes_branch(
        project_root=sender_reaching_the_receiver.project_root,
        plan_identifiers=list(HandedOverPlan),
    )

    assert (
        SenderOriginalPullRequests(
            handover=handover,
            receiver_repository=sender_repository(),
            git=sender_reaching_the_receiver.git,
            client=hosting_client,
        ).read_unmerged()
        == []
    )


def test_branches_are_deleted_once_the_receivers_fork_holds_them(
    sender_reaching_the_receiver: ScratchRepository,
    receivers_fork: ScratchRepository,
    hosting_client: PullRequestHostingClient,
):
    """
    After the import continued every underway item, each original's branch is gone from
    the sender's repository and each original is closed.
    """
    offered = offer_to_receiver(sender_reaching_the_receiver, hosting_client)
    take_over(receivers_fork, hosting_client)

    deletions = originals(
        sender_reaching_the_receiver, hosting_client, offered.handover
    ).delete_continued_branches()

    assert {original.item for original in deletions.deleted} == underway_items(
        offered.handover
    )
    assert deletions.kept == ()
    assert sender_branches(hosting_client) == set()
    assert {
        pull_request["state"]
        for pull_request in hosting_client.sender_pull_requests.values()
    } == {"closed"}


def test_branches_the_receivers_fork_lacks_are_kept(
    sender_reaching_the_receiver: ScratchRepository,
    hosting_client: PullRequestHostingClient,
):
    """
    Before the receiver imports, their fork holds none of the work, so every branch
    stays and no original is closed.
    """
    offered = offer_to_receiver(sender_reaching_the_receiver, hosting_client)
    branches = sender_branches(hosting_client)

    deletions = originals(
        sender_reaching_the_receiver, hosting_client, offered.handover
    ).delete_continued_branches()

    assert deletions.deleted == ()
    assert {original.item for original in deletions.kept} == underway_items(
        offered.handover
    )
    assert sender_branches(hosting_client) == branches
    assert {
        pull_request["state"]
        for pull_request in hosting_client.sender_pull_requests.values()
    } == {"open"}
