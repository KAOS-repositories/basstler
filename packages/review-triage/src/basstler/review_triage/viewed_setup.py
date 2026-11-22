"""
Setting a repository's Actions up to mark pull requests' mechanical files viewed, as
far as a command can, and naming the steps only the user can take.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from basstler.class_property import classproperty
from basstler.git.branch import Branch
from basstler.github.actions_settings import (
    ActionsEnabling,
    ActionsPermissionsRead,
    ActionsSecretRead,
    WorkflowEnabling,
    WorkflowRead,
    WorkflowState,
)
from basstler.github.basstler_project import BasstlerProject
from basstler.github.client import GitHubAttemptClient
from basstler.github.file_proposal import (
    BranchReferenceRead,
    FileCommit,
    FileProposal,
    ProposalOutcome,
)
from basstler.github.repository import Repository
from basstler.github.fork_sync import ForkFastForward
from basstler.github.repository_details import (
    RepositoryDetails,
    RepositoryDetailsRead,
)
from basstler.github.repository_resources import SettingWrite
from basstler.github.token_form import (
    CreateToken,
    PermissionLevel,
    RepositoryPermission,
    SharedToken,
    StoreToken,
    TokenUse,
)
from basstler.github.user_steps import (
    AllowActions,
    MergePullRequest,
    OpenPullRequestFromForm,
    SyncFork,
    UserStep,
)
from basstler.github.workflows import Workflow
from basstler.locations import ReviewTriageLocation, WorkflowLocation
from basstler.render_common import TemplatePage
from basstler.review_triage.exceptions import MarkViewedWorkflowRefused
from basstler.review_triage.viewed_request import ReviewTriageSecret

# %% what each step came to


class SetupState(StrEnum):
    """
    What one step of the setup came to.
    """

    DONE = "done now"
    ALREADY_DONE = "already in place"
    REFUSED = "could not be done"
    UNREADABLE = "could not be read"
    LEFT_TO_USER = "left to you"


class ProposalBranch(StrEnum):
    """
    The branches the setup proposes files on.
    """

    MARK_VIEWED = "basstler/mark-viewed"
    """
    Carries the caller workflow until a reviewer merges it.
    """


@dataclass(frozen=True)
class SetupStep:
    """
    One step of the setup and what it came to.
    """

    description: str
    """
    What the step sets up.
    """

    state: SetupState
    """
    What it came to.
    """

    reason: str = ""
    """
    Why it was refused or left to the user, empty otherwise.
    """


# %% the setup


@dataclass(frozen=True)
class MarkViewedSetup(TemplatePage):
    """
    Sets one repository's Actions up to mark files viewed on another's pull requests.
    """

    workflow_repository: Repository
    """
    The repository whose Actions mark the files and which stores the token.
    """

    pull_request_repository: Repository | None = None
    """
    The repository the pull requests are opened on; the workflow repository's parent,
    or itself, when ``None``.
    """

    branch_or_tag: str = BasstlerProject.default_branch.name
    """
    The basstler branch or tag the installed workflow runs.
    """

    shared_uses: tuple[TokenUse, ...] = ()
    """
    Other jobs of basstler's the person's token may do too; those on the same owner's
    repositories share the token that marks files viewed.
    """

    steps: list[SetupStep] = field(default_factory=list)
    """
    What each step came to, in order, once :meth:`run` ran.
    """

    user_steps: list[UserStep] = field(default_factory=list)
    """
    The steps left to the user, in order, once :meth:`run` ran.
    """

    @classproperty
    def template(cls) -> str:
        return ReviewTriageLocation.MARK_VIEWED_SETUP_TEMPLATE.name

    @property
    def caller_workflow(self) -> str:
        """
        The workflow installed on the workflow repository.
        """
        return (
            self.render_named_template(
                ReviewTriageLocation.MARK_VIEWED_CALLER_TEMPLATE.name,
                reusable_workflow=self.reusable_workflow,
                branch_or_tag=self.branch_or_tag,
                token_secret=ReviewTriageSecret.VIEWER_TOKEN,
            )
            + "\n"
        )

    @property
    def reusable_workflow(self) -> str:
        """
        How the caller workflow names basstler's reusable workflow: as its own file on
        basstler's repository, whose budget counts only such jobs.
        """
        if self.workflow_repository == BasstlerProject.repository:
            return (
                f"{Workflow.local_reference_prefix}"
                f"{WorkflowLocation.REVIEW_TRIAGE_MARK_VIEWED.name}"
            )
        return (
            f"{BasstlerProject.repository.full_name}/"
            f"{WorkflowLocation.REVIEW_TRIAGE_MARK_VIEWED.as_posix()}@{self.branch_or_tag}"
        )

    def run(self, client: GitHubAttemptClient) -> str:
        """
        Take every step a command can, then report them and the steps left.

        :param client: Reads and writes the workflow repository and, for a fork, its
            parent.
        :return: The report, as Markdown.
        :raises MarkViewedWorkflowRefused: If the workflow repository cannot be read.
        """
        read = RepositoryDetailsRead(self.workflow_repository).attempt(client)
        if read.resource is None:
            raise MarkViewedWorkflowRefused(
                self.workflow_repository, read.response.failure.error_message()
            )
        details = read.resource
        installed = self.install_workflow(client, details)
        self.enable_actions(client, details)
        if installed:
            self.enable_workflow(client, details)
        self.check_secret(client, details)
        return self.render_template(
            setup=self, workflow_location=WorkflowLocation.MARK_VIEWED.as_posix()
        )

    # %% the workflow file

    def install_workflow(
        self, client: GitHubAttemptClient, details: RepositoryDetails
    ) -> bool:
        """
        Check that the workflow repository's default branch holds the caller workflow,
        else propose it through a pull request; a fork's is proposed to its parent, and
        the fork is fast-forwarded once its parent holds it.

        :param client: Reads and writes the workflow repository and its parent.
        :param details: The workflow repository.
        :return: Whether its default branch holds the workflow, in any version.
        """
        description = (
            f"the {WorkflowLocation.MARK_VIEWED.name} workflow on "
            f"{self.workflow_repository.full_name}'s {details.default_branch.name}"
        )
        installed = (
            self.workflow_commit(details.default_branch)
            .read_at(details.default_branch.name)
            .attempt(client)
            .resource
        )
        if installed is not None and installed.text == self.caller_workflow:
            self.steps.append(SetupStep(description, SetupState.ALREADY_DONE))
            return True
        if details.parent_default_branch is not None and self.holds_workflow(
            client, details.parent_default_branch
        ):
            return self.fast_forward_fork(
                client, details.parent_default_branch, details, description
            )
        outcome = self.workflow_proposal(details).propose(client)
        self.report_proposal(description, details, outcome)
        return installed is not None

    def holds_workflow(
        self, client: GitHubAttemptClient, parent_default_branch: Branch[Repository]
    ) -> bool:
        """
        :param client: Reads the parent.
        :param parent_default_branch: The default branch of the workflow repository's
            parent.
        :return: Whether that branch holds the caller workflow.
        """
        held = (
            self.workflow_commit(parent_default_branch)
            .read_at(parent_default_branch.name)
            .attempt(client)
            .resource
        )
        return held is not None and held.text == self.caller_workflow

    def fast_forward_fork(
        self,
        client: GitHubAttemptClient,
        parent_default_branch: Branch[Repository],
        details: RepositoryDetails,
        description: str,
    ) -> bool:
        """
        Move the fork's default branch forward to its parent's, which holds the caller
        workflow, leaving the sync to the user where GitHub refuses.

        :param client: Reads the parent and writes the fork.
        :param parent_default_branch: The default branch of the fork's parent.
        :param details: The fork.
        :param description: What installing sets up.
        :return: Whether the fork's default branch holds the workflow now.
        """
        head = BranchReferenceRead(
            parent_default_branch.repository, parent_default_branch
        ).attempt(client)
        if head.resource is None:
            self.steps.append(
                SetupStep(
                    description, SetupState.UNREADABLE, str(head.response.failure)
                )
            )
            self.user_steps.append(SyncFork(self.workflow_repository))
            return False
        write = ForkFastForward(
            repository=self.workflow_repository,
            object_hash=head.resource.target.object_hash,
            branch=details.default_branch,
        )
        answer = client.attempt_send(write)
        if answer.failure is not None:
            self.steps.append(
                SetupStep(description, SetupState.REFUSED, str(answer.failure))
            )
            self.user_steps.append(write.manual_step)
            return False
        self.steps.append(
            SetupStep(
                description,
                SetupState.DONE,
                f"fast-forwarded to {parent_default_branch.repository.full_name}'s "
                f"{parent_default_branch.name}",
            )
        )
        return True

    def workflow_commit(self, branch: Branch[Repository]) -> FileCommit:
        """
        :param branch: The branch the caller workflow is committed on.
        :return: The caller workflow, committed there.
        """
        return FileCommit(
            branch,
            WorkflowLocation.MARK_VIEWED.as_posix(),
            self.caller_workflow,
            "Mark pull requests' mechanical files viewed from Actions",
        )

    def proposal_repository(self, details: RepositoryDetails) -> Repository:
        """
        :param details: The workflow repository.
        :return: The repository the workflow is proposed to: a fork's parent, whose
            default branch the fork follows, else the workflow repository itself.
        """
        if details.parent_default_branch is None:
            return self.workflow_repository
        return details.parent_default_branch.repository

    def workflow_proposal(self, details: RepositoryDetails) -> FileProposal:
        """
        :param details: The workflow repository.
        :return: The caller workflow, on a branch of the workflow repository, proposed
            for the default branch of :meth:`proposal_repository`.
        """
        return FileProposal(
            commit=self.workflow_commit(
                Branch(self.workflow_repository, ProposalBranch.MARK_VIEWED)
            ),
            base=Branch(self.proposal_repository(details), details.default_branch.name),
            description=f"Installed by `basstler review-triage set-up-mark-viewed` "
            f"({self.branch_or_tag}). Merging it lets the workflow mark files viewed "
            f"for the owner of the token stored as `{ReviewTriageSecret.VIEWER_TOKEN}`.",
        )

    def report_proposal(
        self,
        description: str,
        details: RepositoryDetails,
        outcome: ProposalOutcome,
    ) -> None:
        """
        Record the workflow's installation as left to the user, with the step that
        finishes it - merging the pull request or opening it from its form - or as
        refused when GitHub refused both.

        :param description: What installing sets up.
        :param details: The workflow repository.
        :param outcome: What proposing the workflow came to.
        """
        change = f"adding {WorkflowLocation.MARK_VIEWED.name}"
        if outcome.form_url:
            self.steps.append(
                SetupStep(
                    description,
                    SetupState.LEFT_TO_USER,
                    f"its branch {ProposalBranch.MARK_VIEWED} holds it, but no pull "
                    f"request could be opened: {outcome.failure}",
                )
            )
            self.user_steps.append(OpenPullRequestFromForm(outcome.form_url, change))
        elif outcome.pull_request is None:
            self.steps.append(
                SetupStep(
                    description,
                    SetupState.REFUSED,
                    f"no pull request adding it could be opened: {outcome.failure}",
                )
            )
        else:
            self.report_open_proposal(description, details, outcome, change)

    def report_open_proposal(
        self,
        description: str,
        details: RepositoryDetails,
        outcome: ProposalOutcome,
        change: str,
    ) -> None:
        """
        Record the open pull request proposing the workflow, whose merge is left.

        :param description: What installing sets up.
        :param details: The workflow repository.
        :param outcome: The proposal, with its pull request.
        :param change: What the pull request does, as a phrase.
        """
        url = outcome.pull_request.page_url
        found = "opened" if outcome.opened_now else "already open"
        stacked = (
            f", merging into {outcome.merges_into.name}: it reaches "
            f"{details.default_branch.name} once that branch merges"
            if outcome.merges_into is not None
            else ""
        )
        self.steps.append(
            SetupStep(
                description,
                SetupState.LEFT_TO_USER,
                f"pull request {url} adds it ({found}{stacked}); merging it finishes "
                "this step",
            )
        )
        self.user_steps.append(MergePullRequest(url, change))

    # %% the repository's settings

    def enable_actions(
        self, client: GitHubAttemptClient, details: RepositoryDetails
    ) -> None:
        """
        Let a fork run Actions when it does not; for any other repository, leave that
        to the user.

        :param client: Reads and writes the workflow repository.
        :param details: The workflow repository.
        """
        description = f"Actions on {self.workflow_repository.full_name}"
        permissions = ActionsPermissionsRead(self.workflow_repository).attempt(client)
        if permissions.resource is None:
            self.steps.append(
                SetupStep(
                    description,
                    SetupState.UNREADABLE,
                    permissions.response.failure.error_message(),
                )
            )
            self.user_steps.append(
                AllowActions(self.workflow_repository, known_off=False)
            )
            return
        if permissions.resource.enabled:
            self.steps.append(SetupStep(description, SetupState.ALREADY_DONE))
            return
        self.change_setting(
            client,
            details,
            description,
            ActionsEnabling(self.workflow_repository),
            "they are off, and only a fork's settings are changed for you",
        )

    def enable_workflow(
        self, client: GitHubAttemptClient, details: RepositoryDetails
    ) -> None:
        """
        Enable the installed workflow of a fork when GitHub lists it as disabled, as a
        fork's workflows start out; for any other repository, leave that to the user.

        :param client: Reads and writes the workflow repository.
        :param details: The workflow repository.
        """
        description = f"the {WorkflowLocation.MARK_VIEWED.name} workflow enabled"
        listed = WorkflowRead(
            self.workflow_repository, WorkflowLocation.MARK_VIEWED
        ).attempt(client)
        if listed.resource is None:
            self.steps.append(
                SetupStep(
                    description,
                    SetupState.UNREADABLE,
                    listed.response.failure.error_message(),
                )
            )
            return
        if listed.resource.state == WorkflowState.ACTIVE:
            self.steps.append(SetupStep(description, SetupState.ALREADY_DONE))
            return
        self.change_setting(
            client,
            details,
            description,
            WorkflowEnabling(self.workflow_repository, WorkflowLocation.MARK_VIEWED),
            "it is disabled",
        )

    def change_setting(
        self,
        client: GitHubAttemptClient,
        details: RepositoryDetails,
        description: str,
        write: SettingWrite,
        reason_left: str,
    ) -> None:
        """
        Change a fork's setting, leaving its manual step to the user where GitHub
        refuses; leave any other repository's setting to the user unchanged.

        :param client: Writes the workflow repository.
        :param details: The workflow repository.
        :param description: What the setting sets up.
        :param write: The change.
        :param reason_left: Why the change is left to the user on a repository that
            is no fork.
        """
        if not details.is_fork:
            self.steps.append(
                SetupStep(description, SetupState.LEFT_TO_USER, reason_left)
            )
            self.user_steps.append(write.manual_step)
            return
        answer = client.attempt_send(write)
        if answer.failure is None:
            self.steps.append(SetupStep(description, SetupState.DONE))
            return
        self.steps.append(
            SetupStep(description, SetupState.REFUSED, answer.failure.error_message())
        )
        self.user_steps.append(write.manual_step)

    # %% the token

    def check_secret(
        self, client: GitHubAttemptClient, details: RepositoryDetails
    ) -> None:
        """
        Read whether the workflow repository stores the token, leaving its creation
        and storage to the user when it does not or cannot be read.

        :param client: Reads the workflow repository.
        :param details: The workflow repository.
        """
        description = self.secret_description
        stored = ActionsSecretRead(
            self.workflow_repository, ReviewTriageSecret.VIEWER_TOKEN
        ).attempt(client)
        if stored.resource is not None:
            self.steps.append(SetupStep(description, SetupState.ALREADY_DONE))
            return
        self.steps.append(
            SetupStep(description, SetupState.LEFT_TO_USER, "only you can create it")
            if stored.response.is_not_found
            else SetupStep(
                description,
                SetupState.UNREADABLE,
                stored.response.failure.error_message(),
            )
        )
        self.user_steps.extend(
            self.token_steps(details, may_be_done=not stored.response.is_not_found)
        )

    @property
    def secret_description(self) -> str:
        """
        The step storing the token on the workflow repository.
        """
        return (
            f"{ReviewTriageSecret.VIEWER_TOKEN} stored on "
            f"{self.workflow_repository.full_name}"
        )

    @property
    def token_left(self) -> bool:
        """
        Whether :meth:`run` left creating and storing the token to the user.
        """
        return any(
            step.description == self.secret_description
            and step.state != SetupState.ALREADY_DONE
            for step in self.steps
        )

    def token_use(self, details: RepositoryDetails) -> TokenUse:
        """
        :param details: The workflow repository.
        :return: What the token marking files viewed reaches, and where it is stored.
        """
        target = self.target_repository(details)
        return TokenUse(
            f"marks mechanical files of {target.full_name}'s pull requests viewed",
            (target,),
            {
                RepositoryPermission.PULL_REQUESTS: PermissionLevel.WRITE,
                RepositoryPermission.CONTENTS: PermissionLevel.READ,
            },
            ReviewTriageSecret.VIEWER_TOKEN,
            (self.workflow_repository,),
        )

    def token_steps(
        self, details: RepositoryDetails, may_be_done: bool = False
    ) -> tuple[CreateToken, StoreToken]:
        """
        :param details: The workflow repository.
        :param may_be_done: Whether the secret could not be read, so it may be stored
            already.
        :return: Creating the token, for every job of :attr:`shared_uses` it can share,
            and storing it as each of their secrets.
        """
        token = SharedToken.from_requested_use(
            BasstlerProject.name, self.token_use(details), self.shared_uses
        )
        return CreateToken(token, may_be_done), StoreToken(token, may_be_done)

    def target_repository(self, details: RepositoryDetails) -> Repository:
        """
        :param details: The workflow repository.
        :return: The repository the pull requests are opened on.
        """
        if self.pull_request_repository is not None:
            return self.pull_request_repository
        if details.parent_default_branch is not None:
            return details.parent_default_branch.repository
        return self.workflow_repository
