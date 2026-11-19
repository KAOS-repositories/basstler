"""
Where a triage goes once it is made: the interface every output implements, and the
built-in outputs.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Annotated, Any

from pydantic import Field

from basstler.class_property import classproperty
from basstler.github.client import GitHubWriter
from basstler.github.exceptions import GraphQLErrorsReturned
from basstler.github.graphql import GraphQLRequest, GraphQLResponse
from basstler.github.review_models import PageInfo
from basstler.json_model import ValidatedJSONModel
from basstler.locations import ReviewTriageLocation
from basstler.progress import ProgressStep, ProgressUnit
from basstler.render_common import TemplatePage
from basstler.review_triage.declaration import TriageDeclaration
from basstler.review_triage.exceptions import PullRequestHeadMoved
from basstler.review_triage.triage import TriageOutcome
from basstler.standard_streams import StandardStreamHandler
from basstler.text_file import TextFile

logger = StandardStreamHandler.logger_for(__name__)
"""
This module's logger, which the Markdown report prints through.
"""

# %% the interface


class TriageOutput(ABC):
    """
    Delivers a triage outcome somewhere.
    """

    @abstractmethod
    def publish(self, outcome: TriageOutcome) -> None:
        """
        :param outcome: The triaged pull request.
        """


# %% the Markdown report


class MarkdownReport(TriageOutput, TemplatePage):
    """
    Prints the triage as a Markdown report to standard output.
    """

    @classproperty
    def template(cls) -> str:
        return ReviewTriageLocation.REPORT_TEMPLATE.name

    def render(self, outcome: TriageOutcome) -> str:
        """
        :param outcome: The triaged pull request.
        :return: The report.
        """
        return self.render_template(
            outcome=outcome, declaration_marker=TriageDeclaration.marker
        )

    def publish(self, outcome: TriageOutcome) -> None:
        logger.info(self.render(outcome))


class TriageSummary(MarkdownReport):
    """
    Prints only the sentence of :class:`MarkdownReport` counting the files that need
    review.
    """

    @classproperty
    def template(cls) -> str:
        return ReviewTriageLocation.SUMMARY_TEMPLATE.name


# %% marking files viewed


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


class ListedFile(ValidatedJSONModel):
    """
    One file GitHub lists in a pull request.
    """

    path: PurePosixPath
    """
    The file's path in the pull request's head commit.
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


@dataclass(frozen=True)
class ViewedFiles:
    """
    Files of one pull request to mark viewed with one request.
    """

    pull_request_node_identifier: str
    """
    What GitHub's GraphQL API identifies the pull request by.
    """

    paths: tuple[PurePosixPath, ...]
    """
    The files' paths in the pull request's head commit.
    """

    def request(self) -> GraphQLRequest:
        """
        :return: The mutation marking every file of :attr:`paths` viewed, each path
            sent with forward slashes, as GitHub separates them on every platform.
        """
        paths = {
            f"{ViewedFilesVariable.PATH_PREFIX}{position}": path.as_posix()
            for position, path in enumerate(self.paths)
        }
        document = TemplatePage.render_named_template(
            ReviewTriageLocation.MARK_FILES_AS_VIEWED_TEMPLATE.name,
            pull_request_variable=ViewedFilesVariable.PULL_REQUEST,
            path_variables=tuple(paths),
        )
        return GraphQLRequest(
            document,
            {ViewedFilesVariable.PULL_REQUEST: self.pull_request_node_identifier}
            | paths,
        )


@dataclass(frozen=True)
class ViewedMarking(TriageOutput):
    """
    Marks every mechanical file GitHub lists in the pull request viewed, for the account
    whose credential the writer sends.

    :raises PullRequestHeadMoved: Before marking any file, if the pull request was
        pushed to since it was triaged.
    :raises GraphQLErrorsReturned: When GitHub refuses a request.
    """

    github: GitHubWriter
    """
    The writer the requests are sent through.
    """

    files_per_request: int = 50
    """
    How many files one request marks at most.
    """

    def publish(self, outcome: TriageOutcome) -> None:
        refusals = self.refusals(outcome)
        if refusals:
            raise GraphQLErrorsReturned(refusals)

    def refusals(self, outcome: TriageOutcome) -> tuple[str, ...]:
        """
        Mark the mechanical files GitHub lists viewed, stopping at the first refusal.

        :param outcome: The triaged pull request.
        :return: What GitHub refused with, empty once every listed file is marked.
        :raises PullRequestHeadMoved: If its head commit is no longer the triaged one.
        """
        listing = self.listed_paths(outcome)
        if listing.refusals:
            return listing.refusals
        mechanical = [file.change.path for file in outcome.mechanical_files]
        unlisted = [path for path in mechanical if path not in listing.result]
        if unlisted:
            logger.warning(
                "Not marked viewed, as GitHub does not list them in pull request "
                f"{outcome.pull_request.number}: {', '.join(map(str, unlisted))}"
            )
        paths = tuple(path for path in mechanical if path in listing.result)
        with ProgressStep.MARKING_VIEWED.bar(len(paths), ProgressUnit.FILE) as progress:
            for start in range(0, len(paths), self.files_per_request):
                batch = paths[start : start + self.files_per_request]
                marking = self.attempt(
                    ViewedFiles(outcome.pull_request.node_identifier, batch).request()
                )
                if marking.refusals:
                    return marking.refusals
                progress.update(len(batch))
        return ()

    def listed_paths(self, outcome: TriageOutcome) -> AttemptedRequest:
        """
        :param outcome: A triaged pull request.
        :return: The paths of every file GitHub lists in it, as a frozen set.
        :raises PullRequestHeadMoved: If its head commit is no longer the triaged one.
        """
        document = TextFile(ReviewTriageLocation.PULL_REQUEST_FILES).read()
        request = FilesPageRequest(outcome.pull_request.node_identifier)
        paths: set[PurePosixPath] = set()
        while True:
            page = self.attempt(GraphQLRequest(document, request.to_json()))
            if page.refusals:
                return page
            answer = ListedFilesAnswer.from_json(page.result).pull_request
            if answer.head_commit != outcome.pull_request.head.commit:
                raise PullRequestHeadMoved(
                    outcome.pull_request.number,
                    outcome.pull_request.head.commit,
                    answer.head_commit,
                )
            paths.update(file.path for file in answer.files.files)
            if not answer.files.page_info.has_next_page:
                return AttemptedRequest(frozenset(paths))
            request = replace(request, cursor=answer.files.page_info.end_cursor)

    def attempt(self, request: GraphQLRequest) -> AttemptedRequest:
        """
        :param request: The request to send.
        :return: Its result, or what GitHub refused it with.
        """
        response = self.github.attempt_send(request)
        if response.failure is not None:
            return AttemptedRequest(refusals=(response.failure.error_message(),))
        answer = GraphQLResponse.from_json(response.body)
        if answer.errors:
            return AttemptedRequest(
                refusals=tuple(error.message for error in answer.errors)
            )
        return AttemptedRequest(answer.data or {})
