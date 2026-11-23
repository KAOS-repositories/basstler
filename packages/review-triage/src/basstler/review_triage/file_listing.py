"""
The files GitHub lists in a pull request, with whether the account asking has viewed
each, read through GraphQL requests sent again on a server error.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Annotated, Any

from pydantic import Field

from basstler.github.client import GitHubResponse, GitHubWriter, RetryPolicy
from basstler.github.graphql import GraphQLRequest, GraphQLResponse
from basstler.github.review_models import PageInfo
from basstler.json_model import ValidatedJSONModel
from basstler.locations import ReviewTriageLocation
from basstler.text_file import TextFile

# %% the payloads


class ViewedFilesVariable(StrEnum):
    """
    The variables of the mutation marking files of a pull request viewed.
    """

    PULL_REQUEST = "pullRequestId"
    """
    What GitHub's GraphQL API identifies the pull request by.
    """

    PATH_PREFIX = "file"
    """
    What the variable holding each file's path, and the mutation marking it, is named
    by, followed by the file's position in the request.
    """


class PullRequestVariables(ValidatedJSONModel):
    """
    The variables of a GraphQL document about one pull request.
    """

    pull_request_node_identifier: Annotated[
        str, Field(alias=ViewedFilesVariable.PULL_REQUEST)
    ]
    """
    What GitHub's GraphQL API identifies the pull request by.
    """


class FilesPageRequest(PullRequestVariables):
    """
    The variables of the query reading one page of a pull request's files.
    """

    cursor: Annotated[str | None, Field(alias="after")] = None
    """
    The cursor of the page before, ``None`` for the first page.
    """


class FileViewedState(StrEnum):
    """
    Whether the account asking has marked a file of a pull request viewed, as GitHub
    tells.
    """

    VIEWED = "VIEWED"
    """
    Marked viewed, and unchanged since.
    """

    UNVIEWED = "UNVIEWED"
    """
    Never marked viewed.
    """

    DISMISSED = "DISMISSED"
    """
    Marked viewed, then changed by a later commit, which cleared the mark.
    """


class ListedFile(ValidatedJSONModel):
    """
    One file GitHub lists in a pull request.
    """

    path: PurePosixPath
    """
    The file's path in the pull request's head commit.
    """

    viewed_state: Annotated[FileViewedState, Field(alias="viewerViewedState")]
    """
    Whether the account asking has marked it viewed.
    """


class ListedFilesPage(ValidatedJSONModel):
    """
    One page of the files GitHub lists in a pull request.
    """

    files: Annotated[tuple[ListedFile, ...], Field(alias="nodes")]
    """
    The files on this page.
    """

    page_info: Annotated[PageInfo, Field(alias="pageInfo")]
    """
    Whether another page follows, and the cursor to request it with.
    """


class ListedPullRequest(ValidatedJSONModel):
    """
    A pull request as GitHub lists its files, at its head commit now.
    """

    head_commit: Annotated[str, Field(alias="headRefOid")]
    """
    The commit its head branch points at.
    """

    files: ListedFilesPage
    """
    One page of the files it changes.
    """


class ListedFilesAnswer(ValidatedJSONModel):
    """
    The result of the query reading one page of a pull request's files.
    """

    pull_request: Annotated[ListedPullRequest, Field(alias="node")]
    """
    The pull request the query names.
    """


@dataclass(frozen=True)
class AttemptedRequest:
    """
    GitHub's answer to a GraphQL request, or what it refused the request with.
    """

    result: Any = None
    """
    What the request returned, ``None`` when it was refused.
    """

    refusals: tuple[str, ...] = ()
    """
    What GitHub refused the request with, empty when it answered.
    """


# %% sending requests


@dataclass(frozen=True)
class GraphQLAttempts:
    """
    Sends GraphQL requests that change nothing when sent twice, sending each again while
    GitHub answers with a server error.
    """

    github: GitHubWriter
    """
    The writer the requests are sent through.
    """

    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    """
    When a request answered with a server error is sent again.
    """

    def attempt(self, request: GraphQLRequest) -> AttemptedRequest:
        """
        :param request: The request to send.
        :return: Its result, or what GitHub refused it with.
        """
        response = self.send_retrying(request)
        if response.failure is not None:
            return AttemptedRequest(refusals=(response.failure.error_message(),))
        answer = GraphQLResponse.from_json(response.body)
        if answer.errors:
            return AttemptedRequest(
                refusals=tuple(error.message for error in answer.errors)
            )
        return AttemptedRequest(answer.data or {})

    def send_retrying(self, request: GraphQLRequest) -> GitHubResponse:
        """
        :param request: The request to send.
        :return: GitHub's last answer, the request sent again as :attr:`retry_policy`
            says while GitHub answers with a server error.
        """
        response = self.github.attempt_send(request)
        for delay in self.retry_policy.delays():
            if not response.is_server_error:
                break
            time.sleep(delay.total_seconds())
            response = self.github.attempt_send(request)
        return response


# %% reading the listing


@dataclass(frozen=True)
class FileListing:
    """
    The files GitHub lists in a pull request, at the head commit it lists them at.
    """

    head_commit: str
    """
    The commit the pull request's head branch pointed at when listed.
    """

    viewed_states: dict[PurePosixPath, FileViewedState]
    """
    Whether the account asking has viewed each file, by its path.
    """

    def paths_in(self, state: FileViewedState) -> frozenset[PurePosixPath]:
        """
        :param state: A viewed state.
        :return: The files in it.
        """
        return frozenset(
            path for path, listed in self.viewed_states.items() if listed is state
        )


@dataclass(frozen=True)
class FileListingReader:
    """
    Reads the files GitHub lists in a pull request, page by page.
    """

    attempts: GraphQLAttempts
    """
    How each page's request is sent.
    """

    def read(self, pull_request_node_identifier: str) -> AttemptedRequest:
        """
        :param pull_request_node_identifier: What GraphQL identifies the pull request
            by.
        :return: Its :class:`FileListing`, or what GitHub refused a page with.
        """
        document = TextFile(ReviewTriageLocation.PULL_REQUEST_FILES).read()
        request = FilesPageRequest(pull_request_node_identifier)
        states: dict[PurePosixPath, FileViewedState] = {}
        while True:
            page = self.attempts.attempt(GraphQLRequest(document, request.to_json()))
            if page.refusals:
                return page
            answer = ListedFilesAnswer.from_json(page.result).pull_request
            states |= {file.path: file.viewed_state for file in answer.files.files}
            if not answer.files.page_info.has_next_page:
                return AttemptedRequest(FileListing(answer.head_commit, states))
            request = replace(request, cursor=answer.files.page_info.end_cursor)
