"""
The failures of a call to the GitHub REST API, and the ways a workflow breaks the
Actions budget.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path

from basstler.class_property import classproperty
from basstler.credential_origin import CredentialOrigin
from basstler.exceptions import DataclassException, ExternalCallFailed
from basstler.exit_codes import CommandFailure, StackExitCode

REDIRECTION_STATUSES = range(HTTPStatus.MULTIPLE_CHOICES, HTTPStatus.BAD_REQUEST)
"""
Every status of the 3xx class, with which the API answers a path naming a moved resource.
"""


@dataclass
class GitHubCredentialUnavailableError(CommandFailure, RuntimeError):
    """
    Raised when no token is available to authenticate the API calls with.
    """

    @classproperty
    def exit_code(cls) -> StackExitCode:
        """:return: The status this kind of error ends a command with."""
        return StackExitCode.CREDENTIAL_UNAVAILABLE

    variables: tuple[str, ...]
    """
    The environment variables that were consulted.
    """

    def __str__(self) -> str:
        """:return: What was looked for, so the caller can supply it."""
        return (
            f"no GitHub token: set one of {', '.join(self.variables)}, log in with "
            f"`gh auth login`, or run this with a caller that has one"
        )


@dataclass
class GitHubCallFailed(CommandFailure, DataclassException):
    """
    Base for a call to the API that did not succeed.
    """

    @classproperty
    def exit_code(cls) -> StackExitCode:
        """:return: The status this kind of error ends a command with."""
        return StackExitCode.GITHUB_REQUEST_FAILED

    method: str
    """
    The HTTP method used.
    """
    path: str
    """
    The API path called, without the host.
    """

    @property
    def call(self) -> str:
        """:return: The request line, as issued."""
        return f"{self.method} {self.path}"


@dataclass
class GitHubRequestFailed(GitHubCallFailed, ExternalCallFailed):
    """
    Raised when the API refuses a call.
    """

    credential_origin: CredentialOrigin
    """
    Where the token the call authenticated with came from.
    """

    @classmethod
    def for_status(
        cls,
        status: int,
        detail: str,
        method: str,
        path: str,
        credential_origin: CredentialOrigin,
    ) -> GitHubRequestFailed:
        """
        :return: The refusal, a :class:`GitHubCredentialRejected` for a 401 and a
            :class:`GitHubRepositoryMoved` for a redirection.
        """
        refusal = cls
        if status == HTTPStatus.UNAUTHORIZED:
            refusal = GitHubCredentialRejected
        if status in REDIRECTION_STATUSES:
            refusal = GitHubRepositoryMoved
        return refusal(
            status=status,
            detail=detail,
            method=method,
            path=path,
            credential_origin=credential_origin,
        )

    def error_message(self) -> str:
        """
        :return: :meth:`ExternalCallFailed.error_message`, naming the credential.
        """
        return (
            f"{self.call} failed with {self.status} using "
            f"{self.credential_origin.describe_credential()}: "
            f"{self.detail}"
        )


@dataclass
class GitHubCredentialRejected(GitHubRequestFailed):
    """
    Raised when the API rejects the call's token as invalid or expired.
    """

    def error_message(self) -> str:
        """
        :return: That GitHub rejects the credential, unlike
            :meth:`GitHubRequestFailed.error_message`.
        """
        return (
            f"GitHub rejects {self.credential_origin.describe_credential()} as "
            f"invalid or expired: {self.call} failed with {self.status}"
        )

    def suggest_correction(self) -> str:
        """
        :return: How to renew the credential, where
            :meth:`ExternalCallFailed.suggest_correction` has no advice.
        """
        return self.credential_origin.suggest_renewal()


@dataclass
class GitHubRepositoryMoved(GitHubRequestFailed):
    """
    Raised when the API redirects the call because the repository it names was renamed
    or transferred.
    """

    def error_message(self) -> str:
        return (
            f"{self.call} names a repository that moved: GitHub answered "
            f"{self.status} with {self.detail}"
        )

    def suggest_correction(self) -> str:
        return (
            "Look up the repository's new owner and name on github.com, then point the "
            "git remote, configuration or plan that named the old one at it."
        )


@dataclass
class GitHubUnreachableError(GitHubCallFailed, ConnectionError):
    """
    Raised when a call gets no answer from the API, such as when the network is down.
    """

    reason: str
    """
    What stopped the call.
    """

    def error_message(self) -> str:
        return f"{self.call} got no answer from GitHub: {self.reason}"

    def suggest_correction(self) -> str:
        return "Check the network connection to GitHub, then run the command again."


@dataclass
class GraphQLErrorsReturned(DataclassException):
    """
    Raised when GitHub answers a GraphQL request with errors.
    """

    messages: tuple[str, ...]
    """
    Every message GitHub reported.
    """

    def error_message(self) -> str:
        return "GitHub answered with errors: " + "; ".join(self.messages)

    def suggest_correction(self) -> str:
        return (
            "Check that what the request names exists and that the account gh is "
            "logged in as may read or change it: gh auth status"
        )


@dataclass
class BasstlerSourceUnknown(DataclassException):
    """
    Raised when the installed package's metadata names no source repository.
    """

    distribution: str
    """
    The distribution whose metadata was read.
    """

    project_urls: tuple[str, ...]
    """
    Every ``Project-URL`` entry it declares.
    """

    def error_message(self) -> str:
        return (
            f"the {self.distribution} package's metadata names no Source among its "
            f"project URLs ({', '.join(self.project_urls) or 'none'})"
        )

    def suggest_correction(self) -> str:
        return (
            f"Reinstall {self.distribution} from its published release or repository, "
            "whose pyproject.toml declares its Source URL"
        )


# %% reading what a repository owns out of a payload


@dataclass
class RepositoryUnknown(DataclassException, ValueError):
    """
    Raised when a payload names a branch or a pull request but nothing says which
    repository it is of.
    """

    owned_text: str
    """
    The branch or pull request as the payload writes it.
    """

    def error_message(self) -> str:
        return f"no repository is known for {self.owned_text!r}"

    def suggest_correction(self) -> str:
        return (
            "Parse the payload through the read that was served it, so what it names "
            "takes that read's repository; a pull request whose head fork was deleted "
            "names no repository for its head and cannot be read"
        )


# %% reading an upstream pull request


class UpstreamReadError(DataclassException, ABC):
    """
    Base class for every failure reading an upstream pull request.
    """


# %% Actions budget violations


@dataclass
class BudgetViolation(DataclassException):
    """
    One way a workflow breaks the Actions budget, carrying what a reader needs to fix
    it.
    """

    workflow: str
    """
    The file name of the workflow that breaks it.
    """

    def error_message(self) -> str:
        return f"{self.workflow}: {self.problem()}"

    @abstractmethod
    def problem(self) -> str:
        """
        :return: What is wrong with the workflow.
        """


@dataclass
class ScheduledWorkflow(BudgetViolation):
    """
    The workflow runs on a schedule, which nothing in this repository may.
    """

    def problem(self) -> str:
        return "runs on a schedule"

    def suggest_correction(self) -> str:
        return "trigger it on the event it is waiting for instead"


@dataclass
class MissingPullRequestCancellation(BudgetViolation):
    """
    The workflow runs on every push to a pull request without cancelling the run for the
    commit before.
    """

    def problem(self) -> str:
        return "runs on every pull-request push without cancel-in-progress concurrency"

    def suggest_correction(self) -> str:
        return "add a concurrency group with cancel-in-progress: true"


@dataclass
class MissingJobTimeout(BudgetViolation):
    """
    A job that takes a runner declares no ``timeout-minutes``, so a hang holds the
    runner for GitHub's six-hour default.
    """

    job: str
    """
    The job's key.
    """

    def problem(self) -> str:
        return f"job {self.job} has no timeout-minutes"

    def suggest_correction(self) -> str:
        return f"set timeout-minutes on job {self.job}"


@dataclass
class JobTimeoutOverCeiling(BudgetViolation):
    """
    A job's ``timeout-minutes`` is above the workflow's ceiling.
    """

    job: str
    """
    The job's key.
    """

    timeout_minutes: int
    """
    The job's timeout.
    """

    ceiling_minutes: int
    """
    The workflow's ceiling.
    """

    def problem(self) -> str:
        return (
            f"job {self.job} times out after {self.timeout_minutes} minutes, "
            f"above the ceiling of {self.ceiling_minutes}"
        )

    def suggest_correction(self) -> str:
        return (
            f"lower the timeout of job {self.job}, or raise the workflow's ceiling "
            "in the budget file"
        )


@dataclass
class MissingForkGuard(BudgetViolation):
    """
    A first job of a workflow answering ``push`` does not skip a push to a fork.
    """

    job: str
    """
    The job's key.
    """

    condition: str
    """
    The condition the job has to carry.
    """

    def problem(self) -> str:
        return f"job {self.job} does not skip a push to a fork"

    def suggest_correction(self) -> str:
        return (
            f"add `if: {self.condition}` to job {self.job}, or run it in one "
            "repository only with `if: github.repository == '<owner>/<name>'`"
        )


@dataclass
class MissingLabelGuard(BudgetViolation):
    """
    A first job of a workflow answering ``labeled`` runs for any label, without
    comparing the one added.
    """

    job: str
    """
    The job's key.
    """

    def problem(self) -> str:
        return f"job {self.job} runs for any label"

    def suggest_correction(self) -> str:
        return f"compare github.event.label.name in the `if:` of job {self.job}"


@dataclass
class TooManyJobsOnEveryPush(BudgetViolation):
    """
    A workflow running on every push takes runners for more jobs a run than its ceiling
    allows.
    """

    jobs: int
    """
    The most jobs one run takes runners for.
    """

    ceiling: int
    """
    The workflow's ceiling.
    """

    def problem(self) -> str:
        return (
            f"runs up to {self.jobs} jobs on every push, above the ceiling of "
            f"{self.ceiling}"
        )

    def suggest_correction(self) -> str:
        return "narrow its triggers or raise its jobs_per_push_run"


@dataclass
class UncountableJobs(BudgetViolation):
    """
    A workflow running on every push has jobs whose number is only known at run time, so
    its ceiling cannot be checked.
    """

    def problem(self) -> str:
        return (
            "runs on every push with a matrix computed at run time or a reusable "
            "workflow from another repository, so its jobs cannot be counted"
        )

    def suggest_correction(self) -> str:
        return "use a literal matrix and reusable workflows from this repository"


@dataclass
class OverrideWithoutWorkflow(BudgetViolation):
    """
    The budget sets limits for a workflow file the repository does not have.
    """

    def problem(self) -> str:
        return "has limits in the budget but no workflow file"

    def suggest_correction(self) -> str:
        return "remove its override"


@dataclass
class BudgetFileExists(DataclassException, FileExistsError):
    """
    A budget file is already where a new one would be written.

    Once written, the file is reviewed by hand, so writing over it would bless whatever
    the workflows do now.
    """

    path: Path
    """
    The existing file.
    """

    def error_message(self) -> str:
        return f"{self.path} already exists"

    def suggest_correction(self) -> str:
        return "edit it instead of writing a new one"


@dataclass
class MissingBudgetFunction(DataclassException, LookupError):
    """
    A budget file does not define the function that returns its budget.
    """

    path: Path
    """
    The budget file.
    """

    function: str
    """
    The name of the function it has to define.
    """

    def error_message(self) -> str:
        return f"{self.path} defines no {self.function}()"

    def suggest_correction(self) -> str:
        return f"define {self.function}() returning its ActionsBudget"
