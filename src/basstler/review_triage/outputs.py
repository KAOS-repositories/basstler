"""
Where a triage goes once it is made: the interface every output implements, and the
built-in outputs.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Annotated

from pydantic import Field

from basstler.class_property import classproperty
from basstler.github.client import GitHubWriter
from basstler.github.graphql import GraphQLRequest, GraphQLResponse
from basstler.json_model import ValidatedJSONModel
from basstler.locations import ReviewTriageLocation
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


# %% marking files viewed


class ViewedFile(ValidatedJSONModel):
    """
    The variables of the mutation marking one file of a pull request viewed.
    """

    pull_request_node_identifier: Annotated[str, Field(alias="pullRequestId")]
    """
    What GitHub's GraphQL API identifies the pull request by.
    """

    path: PurePosixPath
    """
    The file's path in the pull request's head commit, which GitHub separates with
    forward slashes on every platform.
    """


@dataclass(frozen=True)
class ViewedMarking(TriageOutput):
    """
    Marks every mechanical file viewed for the account whose credential the writer
    sends, raising :class:`GraphQLErrorsReturned` when GitHub refuses one.
    """

    github: GitHubWriter
    """
    The writer the mutations are sent through.
    """

    def publish(self, outcome: TriageOutcome) -> None:
        document = ReviewTriageLocation.MARK_FILE_AS_VIEWED.read_text()
        for file in outcome.mechanical_files:
            variables = ViewedFile(
                outcome.pull_request.node_identifier, file.change.path
            )
            GraphQLResponse.from_json(
                self.github.send(GraphQLRequest(document, variables.to_json()))
            ).result()
