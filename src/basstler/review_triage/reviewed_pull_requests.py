"""
The open pull requests on a repository whose review the credential's account takes part
in.
"""

from __future__ import annotations

from dataclasses import dataclass

from basstler.github.client import GitHubReader
from basstler.github.repository import HasRepository, ReviewerInvolvement
from basstler.json_model import ValidatedJSONModel

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
