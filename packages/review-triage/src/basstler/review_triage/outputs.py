"""
Where a triage goes once it is made: the interface every output implements, and the
built-in outputs.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import PurePosixPath


from basstler.class_property import classproperty
from basstler.github.client import GitHubWriter, RetryPolicy
from basstler.github.exceptions import GraphQLErrorsReturned
from basstler.github.graphql import GraphQLRequest
from basstler.locations import ReviewTriageLocation
from basstler.progress import ProgressStep, ProgressUnit
from basstler.render_common import TemplatePage
from basstler.review_triage.declaration import TriageDeclaration
from basstler.review_triage.exceptions import PullRequestHeadMoved
from basstler.review_triage.file_listing import (
    FileListing,
    FileListingReader,
    GraphQLAttempts,
    ViewedFilesVariable,
)
from basstler.review_triage.triage import TriageOutcome
from basstler.review_triage.viewed_states import ViewedCheckpoints
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

    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    """
    When a request answered with a server error is sent again; reading the files or
    marking one viewed twice changes nothing, so asking again is safe.
    """

    checkpoints: ViewedCheckpoints | None = None
    """
    Where the files marked are recorded as viewed at the head, ``None`` to record
    nothing.
    """

    def publish(self, outcome: TriageOutcome) -> None:
        refusals = self.refusals(outcome)
        if refusals:
            raise GraphQLErrorsReturned(refusals)
        if self.checkpoints is not None:
            self.checkpoints.record(
                outcome.pull_request.head.commit,
                frozenset(file.change.path for file in outcome.mechanical_files),
            )

    @property
    def attempts(self) -> GraphQLAttempts:
        """
        How each request is sent.
        """
        return GraphQLAttempts(self.github, self.retry_policy)

    def refusals(self, outcome: TriageOutcome) -> tuple[str, ...]:
        """
        Mark the mechanical files GitHub lists viewed, stopping at the first refusal.

        :param outcome: The triaged pull request.
        :return: What GitHub refused with, empty once every listed file is marked.
        :raises PullRequestHeadMoved: If its head commit is no longer the triaged one.
        """
        listed = FileListingReader(self.attempts).read(
            outcome.pull_request.node_identifier
        )
        if listed.refusals:
            return listed.refusals
        listing: FileListing = listed.result
        if listing.head_commit != outcome.pull_request.head.commit:
            raise PullRequestHeadMoved(
                outcome.pull_request.number,
                outcome.pull_request.head.commit,
                listing.head_commit,
            )
        mechanical = [file.change.path for file in outcome.mechanical_files]
        unlisted = [path for path in mechanical if path not in listing.viewed_states]
        if unlisted:
            logger.warning(
                "Not marked viewed, as GitHub does not list them in pull request "
                f"{outcome.pull_request.number}: {', '.join(map(str, unlisted))}"
            )
        paths = tuple(path for path in mechanical if path in listing.viewed_states)
        with ProgressStep.MARKING_VIEWED.bar(len(paths), ProgressUnit.FILE) as progress:
            for start in range(0, len(paths), self.files_per_request):
                batch = paths[start : start + self.files_per_request]
                marking = self.attempts.attempt(
                    ViewedFiles(outcome.pull_request.node_identifier, batch).request()
                )
                if marking.refusals:
                    return marking.refusals
                progress.update(len(batch))
        return ()
