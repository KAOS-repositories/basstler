"""
Where a triage goes once it is made: the interface every output implements, and the
built-in outputs.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from pathlib import PurePosixPath
from typing import Annotated

from pydantic import Field

from basstler.class_property import classproperty
from basstler.github.client import GitHubWriter
from basstler.github.graphql import GraphQLRequest, GraphQLResponse
from basstler.github.review_models import PageInfo
from basstler.json_model import ValidatedJSONModel
from basstler.locations import ReviewTriageLocation
from basstler.render_common import TemplatePage
from basstler.review_triage.declaration import TriageDeclaration
from basstler.review_triage.exceptions import PullRequestHeadMoved
from basstler.review_triage.triage import TriageOutcome
from basstler.standard_streams import StandardStreamHandler

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


# %% marking files viewed


class PullRequestVariables(ValidatedJSONModel):
    """
    The variables of a GraphQL document about one pull request.
    """

    pull_request_node_identifier: Annotated[str, Field(alias="pullRequestId")]
    """
    What GitHub's GraphQL API identifies the pull request by.
    """


class ViewedFile(PullRequestVariables):
    """
    The variables of the mutation marking one file of a pull request viewed.
    """

    path: PurePosixPath
    """
    The file's path in the pull request's head commit, which GitHub separates with
    forward slashes on every platform.
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

    def publish(self, outcome: TriageOutcome) -> None:
        listed = self.listed_paths(outcome)
        mechanical = [file.change.path for file in outcome.mechanical_files]
        unlisted = [path for path in mechanical if path not in listed]
        if unlisted:
            logger.warning(
                "Not marked viewed, as GitHub does not list them in pull request "
                f"{outcome.pull_request.number}: {', '.join(map(str, unlisted))}"
            )
        document = ReviewTriageLocation.MARK_FILE_AS_VIEWED.read_text()
        for path in mechanical:
            if path not in listed:
                continue
            variables = ViewedFile(outcome.pull_request.node_identifier, path)
            GraphQLResponse.from_json(
                self.github.send(GraphQLRequest(document, variables.to_json()))
            ).result()

    def listed_paths(self, outcome: TriageOutcome) -> frozenset[PurePosixPath]:
        """
        :param outcome: A triaged pull request.
        :return: The paths of every file GitHub lists in it.
        :raises PullRequestHeadMoved: If its head commit is no longer the triaged one.
        """
        document = ReviewTriageLocation.PULL_REQUEST_FILES.read_text()
        request = FilesPageRequest(outcome.pull_request.node_identifier)
        paths: set[PurePosixPath] = set()
        while True:
            answer = ListedFilesAnswer.from_json(
                GraphQLResponse.from_json(
                    self.github.send(GraphQLRequest(document, request.to_json()))
                ).result()
            ).pull_request
            if answer.head_commit != outcome.pull_request.head.commit:
                raise PullRequestHeadMoved(
                    outcome.pull_request.number,
                    outcome.pull_request.head.commit,
                    answer.head_commit,
                )
            paths.update(file.path for file in answer.files.files)
            if not answer.files.page_info.has_next_page:
                return frozenset(paths)
            request = replace(request, cursor=answer.files.page_info.end_cursor)
