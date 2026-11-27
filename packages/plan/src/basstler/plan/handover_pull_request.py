"""
A plan handover offered as a draft pull request on the receiver's repository, and taken
on from it.

The pull request carries the handover's files for the receiver to review; importing it
saves them onto the receiver's personal-notes branch and closes it unmerged.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import PurePosixPath

from basstler.class_property import classproperty
from basstler.git.branch import Branch
from basstler.git.commands import GitCommandRunner
from basstler.git.remote import Remote
from basstler.git.remote_branch import RemoteBranch
from basstler.github.client import GitHubClient, GitHubReader
from basstler.github.issue import Issue, IssueClosing, IssueComment
from basstler.github.pull_request import NewPullRequest, PullRequestDescription
from basstler.github.pull_request_changes import RestPullRequest
from basstler.github.repository import PullRequestReference, Repository
from basstler.github.repository_access import PullRequestListState
from basstler.plan.locations import PlanHandoverLocation
from basstler.personal_notes.branch import PersonalNotesLocation
from basstler.plan.exceptions import HandoverPullRequestNotChosenError
from basstler.plan.handover import PlanHandover
from basstler.plan.handover_continuation import (
    ContinuedHandover,
    HandoverImport,
    TakenOverComment,
)
from basstler.plan.model import ItemStatus
from basstler.render_common import TemplatePage

# %% the description


@dataclass(frozen=True)
class HandoverPullRequestDescription(TemplatePage):
    """
    The title and description of a handover pull request.
    """

    handover: PlanHandover
    """
    The handover the pull request carries.
    """

    handover_branch: Branch[Repository]
    """
    The branch carrying it.
    """

    receiver_login: str | None
    """
    The GitHub login of the person it is handed to, ``None`` to address no one.
    """

    @classproperty
    def template(cls) -> str:
        return PlanHandoverLocation.PULL_REQUEST_TEMPLATE.name

    @classproperty
    def marker(cls) -> str:
        """
        The line that marks a pull request's description as a handover's.
        """
        return "<!-- basstler:plan-handover -->"

    @property
    def title(self) -> str:
        """
        The pull request's title, naming the plans.
        """
        identifiers = [plan.identifier for plan in self.handover.plans_in_saving_order]
        first, *rest = identifiers
        if not rest:
            return f"Plan handover: {first}"
        return f"Plan handover: {first} and {len(rest)} more plans"

    def render(self) -> str:
        """
        :return: The pull request's description, in Markdown.
        """
        guide = (
            PurePosixPath(PlanHandoverLocation.PULL_REQUEST_DIRECTORY)
            / PlanHandoverLocation.GUIDE
        )
        return self.render_template(
            handover=self.handover,
            receiver_login=self.receiver_login,
            marker=self.marker,
            location=PlanHandoverLocation,
            status=ItemStatus,
            guide_url=self.handover_branch.repository.file_url(
                self.handover_branch, guide.as_posix()
            ),
        )


# %% offering it


@dataclass(frozen=True)
class HandoverOffer:
    """
    A handover offered to its receiver as a draft pull request on their repository, from
    a branch of the sender's.
    """

    handover: PlanHandover
    """
    The handover offered.
    """

    base: Branch[Repository]
    """
    The receiver's branch the pull request is opened against.
    """

    receiver_login: str | None
    """
    The GitHub login of the person it is handed to, ``None`` to address no one.
    """

    git: GitCommandRunner
    """
    The sender's checkout, which pushes the pull request's branch.
    """

    remote: str = "origin"
    """
    The sender's remote the pull request's branch is pushed to.
    """

    @classproperty
    def branch_namespace(cls) -> str:
        """
        The prefix every handover pull request's branch is named under.
        """
        return "basstler/plan-handover"

    @property
    def handover_branch(self) -> Branch[Repository]:
        """
        The sender's branch carrying the handover: one per set of plans, so offering the
        same plans again updates it.
        """
        identifiers = sorted(plan.identifier for plan in self.handover.plans)
        digest = hashlib.sha256(" ".join(identifiers).encode()).hexdigest()[:8]
        first = self.handover.plans_in_saving_order[0].identifier
        return Branch(
            Repository.from_configured_remote(self.git, self.remote),
            f"{self.branch_namespace}/{first}-{digest}",
        )

    def commit_handover_onto_base(self) -> str:
        """
        Commit the handover's files onto the base branch as it is now.

        :raises GitCommandFailed: If the receiver's repository has no base branch.
        :return: The commit.
        """
        base = RemoteBranch(
            Remote(self.git, self.base.repository.clone_url), self.base.name
        )
        base.fetch()
        directory = PurePosixPath(PlanHandoverLocation.PULL_REQUEST_DIRECTORY)
        return self.git.commit_files(
            self.git.commit_at(base.local_reference),
            {
                (directory / path).as_posix(): text.removesuffix("\n")
                for path, text in self.handover.files.items()
            },
            "Hand over plans "
            + ", ".join(
                plan.identifier for plan in self.handover.plans_in_saving_order
            ),
        )

    def push_and_open_pull_request(
        self, *, client: GitHubClient
    ) -> PullRequestReference:
        """
        Push the handover's commit to :attr:`handover_branch` and open a draft pull
        request from it, or update the one already open.

        :param client: Reads and writes the receiver's repository.
        :return: The pull request.
        """
        handover_branch = self.handover_branch
        self.git.run(
            "push",
            "--quiet",
            "--force",
            self.remote,
            f"{self.commit_handover_onto_base()}:{handover_branch.reference}",
        )
        description = HandoverPullRequestDescription(
            handover=self.handover,
            handover_branch=handover_branch,
            receiver_login=self.receiver_login,
        )
        opening = NewPullRequest(
            base=self.base,
            head=handover_branch,
            title=description.title,
            body=description.render(),
        )
        already_open = client.get_entries(
            PullRequestListState.OPEN.path_between(opening)
        )
        if not already_open:
            return PullRequestReference(
                repository=self.base.repository,
                number=Issue.from_json(client.send(opening)).number,
            )
        offered = PullRequestReference(
            repository=self.base.repository,
            number=Issue.from_json(already_open[0]).number,
        )
        client.send(
            PullRequestDescription(
                repository=offered.repository,
                number=offered.number,
                body=opening.body,
            )
        )
        return offered


# %% taking it over


@dataclass(frozen=True)
class HandoverPullRequest(PullRequestReference):
    """
    A handover pull request open on the receiver's repository.
    """

    @classproperty
    def fetched_head_reference(cls) -> str:
        """
        Where the head of the handover pull request last read is kept, so no other fetch
        moves it.
        """
        return "refs/basstler/plan-handover"

    def read_carried_handover(self, *, git: GitCommandRunner) -> PlanHandover:
        """
        :param git: A checkout that can fetch from the pull request's repository.
        :return: The handover its head commit holds.
        """
        git.run(
            "fetch",
            "--quiet",
            "--no-write-fetch-head",
            self.repository.clone_url,
            f"+{self.head_reference}:{self.fetched_head_reference}",
        )
        directory = PurePosixPath(PlanHandoverLocation.PULL_REQUEST_DIRECTORY)
        paths = git.run(
            "ls-tree",
            "-r",
            "--name-only",
            self.fetched_head_reference,
            directory.as_posix(),
        ).splitlines()
        return PlanHandover.from_files(
            {
                PurePosixPath(path).relative_to(directory): git.run(
                    "show", f"{self.fetched_head_reference}:{path}"
                )
                + "\n"
                for path in paths
            }
        )

    def comment_taken_over_and_close(
        self, *, client: GitHubClient, comment: TakenOverComment
    ) -> None:
        """
        Answer the pull request with *comment*, then close it unmerged.

        :param client: Writes the pull request.
        :param comment: What the import did.
        """
        client.send(
            IssueComment(
                repository=self.repository, number=self.number, body=comment.render()
            )
        )
        client.send(IssueClosing(repository=self.repository, number=self.number))


@dataclass(frozen=True)
class HandoverPullRequests:
    """
    The handover pull requests open on the receiver's repository.
    """

    git: GitCommandRunner
    """
    The receiver's checkout.
    """

    remote: str = "origin"
    """
    The receiver's remote naming the repository the pull requests are open on.
    """

    @property
    def repository(self) -> Repository:
        """
        The repository the pull requests are open on.
        """
        return Repository.from_configured_remote(self.git, self.remote)

    def list_open_handover_pull_requests(
        self, *, client: GitHubReader
    ) -> list[HandoverPullRequest]:
        """
        :param client: Reads the repository.
        :return: Every open pull request whose description marks it as a handover's.
        """
        repository = self.repository
        return [
            HandoverPullRequest(repository=repository, number=pull_request.number)
            for pull_request in map(
                RestPullRequest.from_json,
                client.get_entries(PullRequestListState.OPEN.path_on(repository)),
            )
            if HandoverPullRequestDescription.marker in pull_request.description
        ]

    def choose_pull_requests_to_take_over(
        self,
        *,
        client: GitHubReader,
        requested_number: int | None,
        takes_every_one: bool,
    ) -> list[HandoverPullRequest]:
        """
        :param client: Reads the repository.
        :param requested_number: The pull request asked for, ``None`` for the only one.
        :param takes_every_one: Whether to take every open one over.
        :raises HandoverPullRequestNotChosenError: If none is open, the one asked for
            is not, or several are and neither one nor all of them was asked for.
        :return: The pull requests to take over, oldest first.
        """
        offered = self.list_open_handover_pull_requests(client=client)
        chosen = [
            pull_request
            for pull_request in offered
            if takes_every_one or requested_number in (None, pull_request.number)
        ]
        if not chosen or (len(chosen) > 1 and not takes_every_one):
            raise HandoverPullRequestNotChosenError(
                repository=self.repository,
                offered=tuple(offered),
                requested_number=requested_number,
            )
        return sorted(chosen, key=lambda pull_request: pull_request.number)

    def import_and_close(
        self,
        *,
        importing: HandoverImport,
        requested_number: int | None,
        takes_every_one: bool = False,
    ) -> list[ContinuedHandover]:
        """
        Import each chosen pull request's handover, then say so on the pull request and
        close it.

        :param importing: Saves the handovers onto the receiver's notes branch.
        :param requested_number: The pull request asked for, ``None`` for the only one.
        :param takes_every_one: Whether to take every open one over.
        :raises HandoverPullRequestNotChosenError: If no pull request is chosen.
        :raises PlanAlreadyTrackedError: If the notes branch already holds a plan of
            one; that pull request and the ones after it stay open.
        :return: Each handover as taken over, in the order they were.
        """
        notes_branch = PersonalNotesLocation.resolve(
            importing.project_root, os.environ
        ).branch
        taken_over = []
        for pull_request in self.choose_pull_requests_to_take_over(
            client=importing.client,
            requested_number=requested_number,
            takes_every_one=takes_every_one,
        ):
            continued = importing.save(pull_request.read_carried_handover(git=self.git))
            pull_request.comment_taken_over_and_close(
                client=importing.client,
                comment=TakenOverComment(
                    continued=continued, notes_branch=notes_branch
                ),
            )
            taken_over.append(continued)
        return taken_over
