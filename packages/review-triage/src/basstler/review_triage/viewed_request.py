"""
Asking a repository's Actions to mark a pull request's mechanical files viewed, for
sessions that cannot reach GitHub's GraphQL API themselves.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from basstler.github.actions_secret import ActionsSecret
from basstler.github.client import GitHubAttemptClient
from basstler.github.repository_details import RepositoryDetailsRead
from basstler.github.workflow_run import WorkflowDispatch
from basstler.json_model import ValidatedJSONModel
from basstler.review_triage.locations import ReviewTriageWorkflowLocation
from basstler.github.exceptions import GraphQLErrorsReturned
from basstler.github.repository import PullRequestReference, Repository
from basstler.review_triage.exceptions import (
    FilesNotMarkedViewed,
    MarkViewedWorkflowRefused,
)
from basstler.review_triage.outputs import ViewedMarking
from basstler.review_triage.triage import TriageOutcome

# %% names the workflow reads


class ReviewTriageSecret(ActionsSecret):
    """
    The Actions secrets the review triage's workflows read.
    """

    VIEWER_TOKEN = "REVIEW_TRIAGE_VIEWER_TOKEN"
    """
    The token of the account files are marked viewed for, stored on the repository
    whose Actions mark them.
    """


# %% the dispatch


class MarkViewedInputs(ValidatedJSONModel):
    """
    The inputs of the workflow marking a pull request's mechanical files viewed.
    """

    pull_request: str
    """
    The pull request's number, as text like every dispatched input.
    """

    repository: str
    """
    The repository the pull request is opened on, as ``owner/name``.
    """

    @classmethod
    def from_pull_request(cls, pull_request: PullRequestReference) -> MarkViewedInputs:
        """
        :param pull_request: The pull request whose files are marked.
        :return: The inputs naming it, as text like every dispatched input.
        """
        return cls(str(pull_request.number), pull_request.repository.full_name)


class MarkViewedDispatch(WorkflowDispatch):
    """
    A request to run the workflow marking a pull request's mechanical files viewed.
    """

    inputs: MarkViewedInputs
    """
    Which pull request it marks.
    """


@dataclass(frozen=True)
class MarkViewedRequest:
    """
    Asks the workflow of one repository to mark one pull request's mechanical files
    viewed for the account whose token that repository stores.
    """

    workflow_repository: Repository
    """
    The repository whose workflow marks the files.
    """

    pull_request: PullRequestReference
    """
    The pull request whose files are marked.
    """

    def send(self, client: GitHubAttemptClient) -> str:
        """
        :param client: Reads the workflow repository and sends the dispatch.
        :return: The page listing the workflow's runs, where this one's outcome shows.
        :raises MarkViewedWorkflowRefused: If GitHub refuses either call.
        """
        refusal = self.start_workflow_and_return_refusal(client)
        if refusal is not None:
            raise MarkViewedWorkflowRefused(self.workflow_repository, refusal)
        return self.runs_page

    def start_workflow_and_return_refusal(
        self, client: GitHubAttemptClient
    ) -> str | None:
        """
        Start the workflow.

        :param client: Reads the workflow repository and sends the dispatch.
        :return: What GitHub refused either call with, ``None`` once it started.
        """
        details = RepositoryDetailsRead(self.workflow_repository).attempt(client)
        if details.resource is None:
            return details.response.failure.error_message()
        dispatch = client.attempt_send(
            MarkViewedDispatch(
                self.workflow_repository,
                ReviewTriageWorkflowLocation.MARK_VIEWED,
                details.resource.default_branch.name,
                MarkViewedInputs.from_pull_request(self.pull_request),
            )
        )
        if dispatch.failure is not None:
            return dispatch.failure.error_message()
        return None

    @property
    def runs_page(self) -> str:
        """
        The page listing the workflow's runs.
        """
        return self.workflow_repository.workflow_page_url(
            ReviewTriageWorkflowLocation.MARK_VIEWED
        )


# %% marking by whichever route works


class DirectMarkingRefusal(StrEnum):
    """
    Why marking files viewed directly was not even tried.
    """

    IN_CLOUD_SESSION = (
        "not tried, since GitHub's GraphQL API is not reachable from Claude Code cloud "
        "sessions"
    )
    """
    The session runs in a Claude Code cloud container, whose proxy refuses GraphQL.
    """


@dataclass(frozen=True)
class ViewedMarkingRoutes:
    """
    Marks a pull request's mechanical files viewed directly, and where that fails or
    cannot work, through a repository's Actions.
    """

    marking: ViewedMarking
    """
    Marks the files directly.
    """

    request: MarkViewedRequest
    """
    Asks the workflow repository's Actions to mark them.
    """

    client: GitHubAttemptClient
    """
    Sends the request.
    """

    in_cloud_session: bool = False
    """
    Whether this runs in a Claude Code cloud session, which cannot mark them directly.
    """

    directly: bool = False
    """
    Whether to mark them only directly, never through Actions.
    """

    def mark(self, outcome: TriageOutcome) -> str:
        """
        :param outcome: The triaged pull request.
        :return: What was done, as one line.
        :raises GraphQLErrorsReturned: If marking only directly fails.
        :raises FilesNotMarkedViewed: If neither route marks them.
        """
        if self.in_cloud_session:
            direct_refusal = DirectMarkingRefusal.IN_CLOUD_SESSION
        else:
            direct_refusal = "; ".join(self.marking.refusals(outcome))
        pull_request = self.request.pull_request
        if not direct_refusal:
            return (
                f"Marked {len(outcome.mechanical_files)} mechanical files of "
                f"{pull_request.url} viewed"
            )
        if self.directly:
            raise GraphQLErrorsReturned((direct_refusal,))
        workflow_refusal = self.request.start_workflow_and_return_refusal(self.client)
        if workflow_refusal is not None:
            raise FilesNotMarkedViewed(
                pull_request,
                direct_refusal,
                self.request.workflow_repository,
                workflow_refusal,
            )
        return (
            f"Marking directly failed ({direct_refusal}), so "
            f"{self.request.workflow_repository.full_name}'s Actions were asked to mark "
            f"them; the run shows at {self.request.runs_page}"
        )
