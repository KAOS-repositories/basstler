"""
Where a triage goes once it is made: the interface every output implements, and the
built-in outputs.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath

from basstler.class_property import classproperty
from basstler.github.client import GitHubWriter
from basstler.github.exceptions import GraphQLErrorsReturned
from basstler.github.graphql import GraphQLRequest, GraphQLResponse
from basstler.locations import ReviewTriageLocation
from basstler.progress import ProgressStep, ProgressUnit
from basstler.render_common import TemplatePage
from basstler.review_triage.declaration import TriageDeclaration
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
    Marks every mechanical file viewed for the account whose credential the writer
    sends, raising :class:`GraphQLErrorsReturned` when GitHub refuses one or the call.
    """

    github: GitHubWriter
    """
    The writer the mutations are sent through.
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
        Mark the mechanical files viewed, stopping at the first refused request.

        :param outcome: The triaged pull request.
        :return: What GitHub refused with, empty once every file is marked.
        """
        paths = tuple(file.change.path for file in outcome.mechanical_files)
        with ProgressStep.MARKING_VIEWED.bar(len(paths), ProgressUnit.FILE) as progress:
            for start in range(0, len(paths), self.files_per_request):
                batch = paths[start : start + self.files_per_request]
                response = self.github.attempt_send(
                    ViewedFiles(outcome.pull_request.node_identifier, batch).request()
                )
                if response.failure is not None:
                    return (response.failure.error_message(),)
                answer = GraphQLResponse.from_json(response.body)
                if answer.errors:
                    return tuple(error.message for error in answer.errors)
                progress.update(len(batch))
        return ()
