"""
The open pull requests on a repository whose review the credential's account takes part
in.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace

from basstler.git.commands import GitCommandRunner
from basstler.github.client import GitHubReader
from basstler.github.exceptions import GraphQLErrorsReturned
from basstler.github.repository import (
    HasRepository,
    PullRequestReference,
    ReviewerInvolvement,
)
from basstler.json_model import ValidatedJSONModel
from basstler.review_triage.outputs import ViewedMarking
from basstler.review_triage.triage import TriageOutcome
from basstler.review_triage.viewed_states import ViewedCheckpoints

# %% the search's answer


class SearchedPullRequest(ValidatedJSONModel):
    """
    One pull request the issue search found.
    """

    number: int
    """
    Its number on the repository it is opened on.
    """


class PullRequestSearchPage(ValidatedJSONModel):
    """
    One page of the issue search's answer.
    """

    items: tuple[SearchedPullRequest, ...]
    """
    The pull requests found on this page.
    """


# %% the pull requests


@dataclass(frozen=True)
class ReviewedPullRequests(HasRepository):
    """
    The repository's open pull requests that request the credential's account as a
    reviewer or that it has reviewed.
    """

    def numbers(self, github: GitHubReader) -> tuple[int, ...]:
        """
        :param github: Searches the repository's pull requests.
        :return: Their numbers, each once, lowest first.
        """
        return tuple(
            sorted(
                {
                    pull_request.number
                    for involvement in ReviewerInvolvement
                    for page in github.get_pages(
                        self.repository.reviewer_pull_request_search_path(involvement)
                    )
                    for pull_request in PullRequestSearchPage.from_json(page).items
                }
            )
        )

    def mark_viewed(
        self,
        marking: ViewedMarking,
        git: GitCommandRunner,
        outcomes: Iterable[TriageOutcome],
    ) -> str:
        """
        Mark each triaged pull request's mechanical files viewed, recording each in its
        own checkpoints, going on past a refused one.

        :param marking: Marks one pull request's files.
        :param git: The clone whose state keeps the checkpoints.
        :param outcomes: The pull requests, triaged.
        :return: What was marked, one line per pull request.
        :raises GraphQLErrorsReturned: Once every one was tried, if any was refused.
        """
        marked: list[str] = []
        refusals: list[str] = []
        for outcome in outcomes:
            number = outcome.pull_request.number
            url = PullRequestReference(self.repository, number).url
            checkpoints = ViewedCheckpoints.for_pull_request(
                git, self.repository, number
            )
            refused = replace(marking, checkpoints=checkpoints).mark(outcome)
            if refused:
                refusals.extend(f"{url}: {refusal}" for refusal in refused)
                continue
            marked.append(
                f"Marked {len(outcome.mechanical_files)} mechanical files of {url} "
                "viewed"
            )
        if refusals:
            raise GraphQLErrorsReturned(tuple(refusals))
        return "\n".join(marked)
