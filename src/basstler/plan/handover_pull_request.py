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
from enum import StrEnum
from pathlib import Path, PurePosixPath

from basstler.class_property import classproperty
from basstler.git.commands import GitCommandRunner
from basstler.github.client import GitHubClient, GitHubReader
from basstler.github.issue import Issue, IssueClosing, IssueComment
from basstler.github.pull_request import NewPullRequest, PullRequestDescription
from basstler.github.pull_request_changes import RestPullRequest
from basstler.github.repository import Repository, RepositoryBranch
from basstler.github.repository_access import PullRequestListState
from basstler.locations import PlanHandoverLocation
from basstler.personal_notes.branch import PersonalNotesLocation
from basstler.plan.exceptions import HandoverPullRequestNotChosenError
from basstler.plan.handover import PlanHandover
from basstler.plan.model import ItemStatus
from basstler.render_common import TemplatePage

# %% where it is kept


class HandoverReference(StrEnum):
    """
    Where a handover keeps a commit it fetched, so no other fetch moves it.
    """

    BASE = "refs/basstler/plan-handover-base"
    """
    The branch a handover pull request is opened against, as the offer last fetched it.
    """

    OFFERED = "refs/basstler/plan-handover"
    """
    The head of the handover pull request an import last fetched.
    """


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

    head: RepositoryBranch
    """
    The branch carrying it.
    """

    receiver: str | None
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
            receiver=self.receiver,
            marker=self.marker,
            location=PlanHandoverLocation,
            status=ItemStatus,
            guide_url=self.head.repository.file_url(self.head, guide.as_posix()),
        )


# %% offering it


@dataclass(frozen=True)
class HandoverOffer:
    """
    A handover offered to its receiver as a draft pull request on their repository,
    from a branch of the sender's.
    """

    handover: PlanHandover
    """
    The handover offered.
    """

    base: RepositoryBranch
    """
    The receiver's branch the pull request is opened against.
    """

    receiver: str | None
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
    def head(self) -> RepositoryBranch:
        """
        The branch carrying the handover: one per set of plans, so offering the same
        plans again updates it.
        """
        identifiers = sorted(plan.identifier for plan in self.handover.plans)
        digest = hashlib.sha256(" ".join(identifiers).encode()).hexdigest()[:8]
        first = self.handover.plans_in_saving_order[0].identifier
        return RepositoryBranch(
            repository=Repository.from_configured_remote(self.git, self.remote),
            name=f"{self.branch_namespace}/{first}-{digest}",
        )

    def commit(self) -> str:
        """
        Commit the handover's files onto the base branch as it is now.

        :return: The commit.
        """
        self.git.run(
            "fetch",
            "--quiet",
            "--no-write-fetch-head",
            self.base.repository.clone_url,
            f"+refs/heads/{self.base.name}:{HandoverReference.BASE}",
        )
        directory = PurePosixPath(PlanHandoverLocation.PULL_REQUEST_DIRECTORY)
        return self.git.commit_files(
            self.git.commit_at(HandoverReference.BASE),
            {
                (directory / path).as_posix(): text.removesuffix("\n")
                for path, text in self.handover.files.items()
            },
            "Hand over plans "
            + ", ".join(
                plan.identifier for plan in self.handover.plans_in_saving_order
            ),
        )

    def offer(self, *, client: GitHubClient) -> Issue:
        """
        Push the handover's commit to :attr:`head` and open a draft pull request from
        it, or update the one already open.

        :param client: Reads and writes the receiver's repository.
        :return: The pull request.
        """
        head = self.head
        self.git.run(
            "push",
            "--quiet",
            "--force",
            self.remote,
            f"{self.commit()}:refs/heads/{head.name}",
        )
        description = HandoverPullRequestDescription(
            handover=self.handover, head=head, receiver=self.receiver
        )
        opening = NewPullRequest(
            base=self.base,
            head=head,
            title=description.title,
            body=description.render(),
        )
        already_open = client.get_pages(PullRequestListState.OPEN.path_between(opening))
        if not already_open:
            return Issue.from_json(client.send(opening))
        offered = Issue.from_json(already_open[0])
        client.send(
            PullRequestDescription(
                repository=self.base.repository,
                number=offered.number,
                body=opening.body,
            )
        )
        return offered


# %% taking it over


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

    def offered(self, *, client: GitHubReader) -> list[RestPullRequest]:
        """
        :param client: Reads the repository.
        :return: Every open pull request whose description marks it as a handover's.
        """
        return [
            pull_request
            for pull_request in map(
                RestPullRequest.from_json,
                client.get_pages(PullRequestListState.OPEN.path_on(self.repository)),
            )
            if HandoverPullRequestDescription.marker in pull_request.description
        ]

    def chosen(
        self, *, client: GitHubReader, requested_number: int | None
    ) -> RestPullRequest:
        """
        :param client: Reads the repository.
        :param requested_number: The pull request asked for, ``None`` for the only one.
        :raises HandoverPullRequestNotChosenError: If no single offered pull request
            matches.
        :return: The pull request to take over.
        """
        offered = self.offered(client=client)
        matching = [
            pull_request
            for pull_request in offered
            if requested_number in (None, pull_request.number)
        ]
        if len(matching) != 1:
            raise HandoverPullRequestNotChosenError(
                repository=self.repository,
                offered_numbers=tuple(pull_request.number for pull_request in offered),
                requested_number=requested_number,
            )
        return matching[0]

    def handover_carried_by(self, pull_request: RestPullRequest) -> PlanHandover:
        """
        :param pull_request: An offered pull request.
        :return: The handover its head commit holds.
        """
        self.git.run(
            "fetch",
            "--quiet",
            "--no-write-fetch-head",
            self.remote,
            f"+{pull_request.head_reference}:{HandoverReference.OFFERED}",
        )
        directory = PurePosixPath(PlanHandoverLocation.PULL_REQUEST_DIRECTORY)
        paths = self.git.run(
            "ls-tree",
            "-r",
            "--name-only",
            HandoverReference.OFFERED,
            directory.as_posix(),
        ).splitlines()
        return PlanHandover.from_files(
            {
                PurePosixPath(path).relative_to(directory): self.git.run(
                    "show", f"{HandoverReference.OFFERED}:{path}"
                )
                + "\n"
                for path in paths
            }
        )

    def take_over(
        self, *, client: GitHubClient, requested_number: int | None, project_root: Path
    ) -> PlanHandover:
        """
        Save the chosen pull request's handover onto the receiver's notes branch, then
        say so on the pull request and close it.

        :param client: Reads and writes the repository.
        :param requested_number: The pull request asked for, ``None`` for the only one.
        :param project_root: The receiver's checkout, whose notes branch receives it.
        :raises HandoverPullRequestNotChosenError: If no single offered pull request
            matches.
        :raises PlanAlreadyTrackedError: If the notes branch already holds one of its
            plans; the pull request stays open.
        :return: The handover taken over.
        """
        pull_request = self.chosen(client=client, requested_number=requested_number)
        handover = self.handover_carried_by(pull_request)
        handover.save_to_notes_branch(project_root=project_root)
        notes_branch = PersonalNotesLocation.resolve(project_root, os.environ).branch
        client.send(
            IssueComment(
                repository=self.repository,
                number=pull_request.number,
                body=(
                    f"Taken over onto `{notes_branch}` with "
                    "`basstler plan-handover import`."
                ),
            )
        )
        client.send(
            IssueClosing(repository=self.repository, number=pull_request.number)
        )
        return handover
