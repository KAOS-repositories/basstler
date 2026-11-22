"""
Setting a repository's Actions up to mark files viewed, and the steps left to the user.
"""

from __future__ import annotations

import base64
from http import HTTPStatus
from pathlib import Path
from typing import Any

import pytest

from basstler.github.actions_secret import ActionsSecret
from basstler.github.permission_level import PermissionLevel
from basstler.git.branch import Branch
from basstler.github.actions_settings import (
    ActionsEnabling,
    WorkflowEnabling,
    WorkflowState,
)
from basstler.github.basstler_project import BasstlerProject
from basstler.github.client import (
    GitHubWrite,
)
from basstler.github.file_proposal import FileWrite, NewBranch
from basstler.github.fork_sync import ForkFastForward
from basstler.github.pull_request import NewPullRequest
from basstler.github.repository import Repository, RepositoryBranch
from basstler.github.workflows import TriggerEvent, Workflow
from basstler.github.repository_details import RepositoryDetails
from basstler.github.token_form import (
    RepositoryPermission,
    TokenUse,
)
from basstler.github.user_steps import (
    AllowActions,
    EnableWorkflow,
    MergePullRequest,
    SyncFork,
)
from basstler.locations import WorkflowLocation
from basstler.review_triage.exceptions import MarkViewedWorkflowRefused
from basstler.review_triage.viewed_request import ReviewTriageSecret
from basstler.review_triage.viewed_setup import (
    MarkViewedSetup,
    ProposalBranch,
    SetupState,
)

from basstler_testing.constants.paths import RepositoryLocation
from basstler_testing.github.path_answering_client import PathAnsweringClient
from .conftest import WORKFLOW_REPOSITORY_DETAILS

# %% a stand-in for GitHub

ANOTHER_RELEASE = "v1.0.0"
"""
A basstler release other than the default the setup installs the workflow at.
"""

FORK = Repository("a-reviewer", "project")
"""
The repository whose Actions are set up.
"""

UPSTREAM = Repository("an-organisation", "project")
"""
The repository the fork was made from, where the pull requests are opened.
"""

STAND_IN_DEFAULT_BRANCH = RepositoryDetails.from_json(
    WORKFLOW_REPOSITORY_DETAILS
).default_branch
"""
The default branch of every stand-in repository.
"""

WORKFLOW_PROPOSAL_BRANCH = Branch(ProposalBranch.MARK_VIEWED)
"""
The branch the setup proposes the workflow on.
"""

WORKFLOW_FILE_PATH = WorkflowLocation.MARK_VIEWED.as_posix()
"""
The workflow file's path from the repository's root.
"""


class Resource:
    """
    The REST paths the setup reads on the workflow repository.
    """

    WORKFLOW_FILE = FORK.contents_path(WORKFLOW_FILE_PATH, STAND_IN_DEFAULT_BRANCH.name)
    ACTIONS = FORK.actions_permissions_path
    PROPOSAL_BRANCH = FORK.branch_reference_path(WORKFLOW_PROPOSAL_BRANCH)
    DEFAULT_BRANCH = FORK.branch_reference_path(STAND_IN_DEFAULT_BRANCH)
    PROPOSED_FILE = FORK.contents_path(
        WORKFLOW_FILE_PATH, WORKFLOW_PROPOSAL_BRANCH.name
    )
    WORKFLOW = FORK.workflow_resource_path(WorkflowLocation.MARK_VIEWED)
    SECRET = ReviewTriageSecret.VIEWER_TOKEN.path_on(FORK)


def fork_details(is_fork: bool = True) -> dict[str, Any]:
    """
    :param is_fork: Whether the repository is a fork of :data:`UPSTREAM`.
    :return: Its REST resource.
    """
    details = dict(WORKFLOW_REPOSITORY_DETAILS, fork=is_fork)
    if is_fork:
        details["parent"] = {
            "full_name": UPSTREAM.full_name,
            "default_branch": STAND_IN_DEFAULT_BRANCH.name,
        }
    return details


INSTALLED_BLOB = "a-blob"
"""
The blob the installed workflow file holds.
"""


def installed_workflow(setup: MarkViewedSetup) -> dict[str, Any]:
    """
    :param setup: The setup whose workflow is installed.
    :return: The contents API's answer for that workflow file.
    """
    content = base64.encodebytes(setup.caller_workflow.encode()).decode()
    return {"sha": INSTALLED_BLOB, "content": content}


def answers(**overrides: Any) -> PathAnsweringClient:
    """
    :param overrides: Answers replacing the fully set-up fork's, ``None`` to refuse
        that path.
    :return: The fork answering as fully set up, apart from *overrides*.
    """
    readable = {
        FORK.api_path: fork_details(),
        Resource.WORKFLOW_FILE: installed_workflow(MarkViewedSetup(FORK)),
        Resource.ACTIONS: {"enabled": True},
        Resource.WORKFLOW: {"state": WorkflowState.ACTIVE},
        Resource.SECRET: {"name": ReviewTriageSecret.VIEWER_TOKEN},
    }
    readable |= {getattr(Resource, name): answer for name, answer in overrides.items()}
    return PathAnsweringClient(
        {path: body for path, body in readable.items() if body is not None}
    )


def branch_at_base(branch: Branch) -> dict[str, Any]:
    """
    :param branch: A branch of the repository.
    :return: The branch, as the git references API returns it, pointing at the base.
    """
    return {"ref": branch.reference, "object": {"sha": BASE_COMMIT}}


def sent_of(client: PathAnsweringClient, kind: type[GitHubWrite]) -> list[GitHubWrite]:
    """
    :param client: The stand-in the setup ran against.
    :param kind: The kind of write.
    :return: Every write of that kind sent, oldest first.
    """
    return [write for write in client.sent if isinstance(write, kind)]


# %% taking the steps


def test_a_set_up_fork_is_left_alone():
    client = answers()
    setup = MarkViewedSetup(FORK)
    setup.run(client)
    assert (client.sent, setup.user_steps) == ([], [])
    assert {step.state for step in setup.steps} == {SetupState.ALREADY_DONE}


# %% a fork, whose workflow is proposed to its parent


BASE_COMMIT = "a-base-commit"
"""
The commit the default branch points at.
"""


def fork_proposal_answers(**overrides: Any) -> PathAnsweringClient:
    """
    :param overrides: Answers replacing the fork's, as for :func:`answers`.
    :return: A fork lacking the workflow, whose parent holds no proposal of it.
    """
    client = answers(**({"WORKFLOW_FILE": None, "WORKFLOW": None} | overrides))
    setup = MarkViewedSetup(FORK)
    proposal = setup.workflow_proposal(RepositoryDetails.from_json(fork_details()))
    client.answers[proposal.open_pull_requests_path] = []
    client.answers[proposal.open_from_branch_path] = []
    client.answers[UPSTREAM.branch_reference_path(STAND_IN_DEFAULT_BRANCH)] = (
        branch_at_base(STAND_IN_DEFAULT_BRANCH)
    )
    client.write_answers[UPSTREAM.pull_requests_path] = {
        "number": 3,
        "html_url": UPSTREAM.pull_request_url(3),
    }
    return client


def test_a_fork_s_default_branch_is_never_written():
    client = fork_proposal_answers()
    MarkViewedSetup(FORK).run(client)
    assert [
        write.branch.name
        for write in sent_of(client, FileWrite)
        if write.repository == FORK
    ] == [WORKFLOW_PROPOSAL_BRANCH.name]


def test_a_fork_s_workflow_is_proposed_to_its_parent_from_a_fork_branch():
    client = fork_proposal_answers()
    setup = MarkViewedSetup(FORK)
    setup.run(client)
    proposal = setup.workflow_proposal(RepositoryDetails.from_json(fork_details()))
    assert sent_of(client, NewPullRequest) == [
        NewPullRequest(
            base=RepositoryBranch(STAND_IN_DEFAULT_BRANCH.name, UPSTREAM),
            head=RepositoryBranch(WORKFLOW_PROPOSAL_BRANCH.name, FORK),
            title=proposal.commit.message,
            body=proposal.description,
            draft=False,
        )
    ]


def test_a_fork_s_proposal_branch_starts_at_its_parent_s_default_branch():
    client = fork_proposal_answers()
    MarkViewedSetup(FORK).run(client)
    assert sent_of(client, NewBranch) == [
        NewBranch(
            repository=FORK,
            object_hash=BASE_COMMIT,
            name=WORKFLOW_PROPOSAL_BRANCH.name,
        )
    ]


def test_a_fork_s_proposal_leaves_only_its_merge():
    setup = MarkViewedSetup(FORK)
    setup.run(fork_proposal_answers())
    assert setup.user_steps == [
        MergePullRequest(
            UPSTREAM.pull_request_url(3),
            f"adding {WorkflowLocation.MARK_VIEWED.name}",
        )
    ]


def merged_upstream_answers(**overrides: Any) -> PathAnsweringClient:
    """
    :param overrides: Answers replacing the fork's, as for :func:`answers`.
    :return: A fork lacking the workflow, whose parent's default branch holds it.
    """
    client = fork_proposal_answers(**overrides)
    client.answers[
        UPSTREAM.contents_path(WORKFLOW_FILE_PATH, STAND_IN_DEFAULT_BRANCH.name)
    ] = installed_workflow(MarkViewedSetup(FORK))
    return client


def test_a_fork_whose_parent_holds_the_workflow_is_fast_forwarded_to_it():
    client = merged_upstream_answers()
    MarkViewedSetup(FORK).run(client)
    assert sent_of(client, ForkFastForward) == [
        ForkFastForward(
            repository=FORK, object_hash=BASE_COMMIT, branch=STAND_IN_DEFAULT_BRANCH
        )
    ]


def test_a_fast_forwarded_fork_has_its_workflow_enabled():
    client = merged_upstream_answers(WORKFLOW={"state": "disabled_fork"})
    MarkViewedSetup(FORK).run(client)
    assert sent_of(client, WorkflowEnabling) == [
        WorkflowEnabling(FORK, WorkflowLocation.MARK_VIEWED)
    ]


def test_a_refused_fast_forward_leaves_the_sync_to_the_user():
    client = merged_upstream_answers()
    client.write_refusal = HTTPStatus.UNPROCESSABLE_ENTITY
    setup = MarkViewedSetup(FORK)
    setup.run(client)
    assert setup.user_steps[0] == SyncFork(FORK)


def test_a_fork_holding_another_version_gets_it_proposed_not_replaced():
    client = fork_proposal_answers(
        WORKFLOW_FILE=installed_workflow(MarkViewedSetup(FORK)), WORKFLOW=None
    )
    setup = MarkViewedSetup(FORK, branch_or_tag=ANOTHER_RELEASE)
    setup.run(client)
    assert [
        (write.branch.name, write.text) for write in sent_of(client, FileWrite)
    ] == [(WORKFLOW_PROPOSAL_BRANCH.name, setup.caller_workflow)]


# %% a repository that is no fork


PROPOSAL = {"number": 7, "html_url": FORK.pull_request_url(7)}
"""
The pull request proposing the workflow.
"""


def unforked_answers(**overrides: Any) -> PathAnsweringClient:
    """
    :param overrides: Answers replacing the unset-up repository's, as for
        :func:`answers`.
    :return: A repository that is no fork, lacking the workflow and any proposal of it.
    """
    proposal = MarkViewedSetup(FORK).workflow_proposal(
        RepositoryDetails.from_json(fork_details(is_fork=False))
    )
    unset_up = {
        "WORKFLOW_FILE": None,
        "DEFAULT_BRANCH": branch_at_base(STAND_IN_DEFAULT_BRANCH),
    }
    client = answers(**(unset_up | overrides))
    client.answers.setdefault(proposal.open_from_branch_path, [])
    client.answers[FORK.api_path] = fork_details(is_fork=False)
    client.write_answers[FORK.pull_requests_path] = PROPOSAL
    return client


def test_a_repository_that_is_no_fork_gets_a_pull_request_adding_the_workflow():
    client = unforked_answers()
    setup = MarkViewedSetup(FORK)
    setup.run(client)
    proposal = setup.workflow_proposal(
        RepositoryDetails.from_json(fork_details(is_fork=False))
    )
    assert [
        write
        for write in client.sent
        if isinstance(write, (NewBranch, FileWrite, NewPullRequest))
    ] == [
        NewBranch(
            repository=FORK,
            object_hash=BASE_COMMIT,
            name=WORKFLOW_PROPOSAL_BRANCH.name,
        ),
        proposal.commit.write_replacing(None),
        NewPullRequest(
            base=RepositoryBranch(STAND_IN_DEFAULT_BRANCH.name, FORK),
            head=RepositoryBranch(WORKFLOW_PROPOSAL_BRANCH.name, FORK),
            title=proposal.commit.message,
            body=proposal.description,
            draft=False,
        ),
    ]


def test_merging_the_proposal_is_the_step_left():
    setup = MarkViewedSetup(FORK)
    setup.run(unforked_answers())
    assert setup.user_steps[0].browser_steps[0] == f"Open {PROPOSAL['html_url']}."


def test_an_open_proposal_is_not_opened_again():
    setup = MarkViewedSetup(FORK)
    proposal = setup.workflow_proposal(
        RepositoryDetails.from_json(fork_details(is_fork=False))
    )
    client = unforked_answers(
        PROPOSAL_BRANCH=branch_at_base(WORKFLOW_PROPOSAL_BRANCH),
        PROPOSED_FILE=installed_workflow(setup),
    )
    client.answers[proposal.open_from_branch_path] = [PROPOSAL]
    setup.run(client)
    assert client.sent == []


def test_a_proposal_branch_holding_another_version_is_updated():
    setup = MarkViewedSetup(FORK, branch_or_tag=ANOTHER_RELEASE)
    client = unforked_answers(
        PROPOSAL_BRANCH=branch_at_base(WORKFLOW_PROPOSAL_BRANCH),
        PROPOSED_FILE=installed_workflow(MarkViewedSetup(FORK)),
    )
    setup.run(client)
    assert [
        (write.branch.name, write.replaced_object_hash)
        for write in sent_of(client, FileWrite)
    ] == [(WORKFLOW_PROPOSAL_BRANCH.name, INSTALLED_BLOB)]


def test_a_refused_proposal_is_reported_as_refused():
    client = unforked_answers()
    client.write_refusal = HTTPStatus.FORBIDDEN
    setup = MarkViewedSetup(FORK)
    setup.run(client)
    assert setup.steps[0].state == SetupState.REFUSED


def test_a_refused_proposal_leaves_no_file_to_commit_by_hand():
    client = unforked_answers(WORKFLOW_FILE=installed_workflow(MarkViewedSetup(FORK)))
    client.write_refusal = HTTPStatus.FORBIDDEN
    setup = MarkViewedSetup(FORK, branch_or_tag=ANOTHER_RELEASE)
    setup.run(client)
    assert setup.user_steps == []


def test_actions_turned_off_are_turned_on():
    client = answers(ACTIONS={"enabled": False})
    MarkViewedSetup(FORK).run(client)
    assert client.sent == [ActionsEnabling(FORK)]


def test_a_disabled_workflow_is_enabled():
    client = answers(WORKFLOW={"state": "disabled_fork"})
    MarkViewedSetup(FORK).run(client)
    assert client.sent == [WorkflowEnabling(FORK, WorkflowLocation.MARK_VIEWED)]


def test_a_refused_setting_leaves_its_manual_step():
    client = answers(ACTIONS={"enabled": False})
    client.write_refusal = HTTPStatus.FORBIDDEN
    setup = MarkViewedSetup(FORK)
    setup.run(client)
    assert setup.user_steps == [ActionsEnabling(FORK).manual_step]


def test_a_missing_secret_leaves_creating_and_storing_the_token():
    setup = MarkViewedSetup(FORK)
    setup.run(answers(SECRET=None))
    create, store = setup.user_steps
    assert f"={UPSTREAM.owner}&" in create.browser_steps[0]
    assert RepositoryPermission.PULL_REQUESTS in create.browser_steps[0]
    assert store.command == (
        f"gh secret set {ReviewTriageSecret.VIEWER_TOKEN} --repo {FORK.full_name}"
    )


def test_an_unreadable_repository_is_raised():
    client = PathAnsweringClient()
    with pytest.raises(MarkViewedWorkflowRefused):
        MarkViewedSetup(FORK).run(client)


def test_the_report_names_every_step_left_as_written():
    """
    Each step left is in the report, only its first letter capitalised.
    """
    setup = MarkViewedSetup(FORK)
    report = setup.run(answers(SECRET=None))
    named = [
        f"{step.description[0].upper()}{step.description[1:]}:" in report
        for step in setup.user_steps
    ]
    assert named == [True, True]


def test_the_settings_of_a_repository_that_is_no_fork_are_left_to_the_user():
    client = answers(
        ACTIONS={"enabled": False}, WORKFLOW={"state": "disabled_manually"}
    )
    client.answers[FORK.api_path] = fork_details(is_fork=False)
    setup = MarkViewedSetup(FORK)
    setup.run(client)
    assert (client.sent, setup.user_steps) == (
        [],
        [
            AllowActions(FORK, known_off=True),
            EnableWorkflow(FORK, WorkflowLocation.MARK_VIEWED),
        ],
    )


def test_unreadable_actions_settings_are_never_changed_or_called_off():
    client = answers(ACTIONS=None)
    setup = MarkViewedSetup(FORK)
    setup.run(client)
    assert client.sent == []
    actions = f"Actions on {FORK.full_name}"
    assert [step.state for step in setup.steps if step.description == actions] == [
        SetupState.UNREADABLE
    ]


def test_an_unreadable_secret_is_reported_unread_with_the_token_steps_left():
    client = answers()
    client.forbidden.add(Resource.SECRET)
    setup = MarkViewedSetup(FORK)
    setup.run(client)
    assert (
        [
            step.state
            for step in setup.steps
            if step.description == setup.secret_description
        ],
        setup.user_steps,
    ) == (
        [SetupState.UNREADABLE],
        list(
            setup.token_steps(
                RepositoryDetails.from_json(fork_details()), may_be_done=True
            )
        ),
    )


def test_basstler_s_own_caller_is_the_workflow_the_setup_writes():
    """
    Basstler's own repository runs the workflow the setup writes.
    """
    installed = (RepositoryLocation.ROOT / WorkflowLocation.MARK_VIEWED).read_text(
        encoding="utf-8"
    )
    assert installed == MarkViewedSetup(BasstlerProject.repository).caller_workflow


# %% when the workflow runs


def test_the_workflow_runs_only_when_started(tmp_path: Path):
    """
    The files are marked when someone asks, never by a pull request event.
    """
    written = tmp_path / WorkflowLocation.MARK_VIEWED.name
    written.write_text(MarkViewedSetup(FORK).caller_workflow, encoding="utf-8")
    assert [trigger.event for trigger in Workflow.at(written).triggers] == [
        TriggerEvent.WORKFLOW_DISPATCH
    ]


# %% one token for several jobs


class AnotherJobSecret(ActionsSecret):
    """
    The secret another job of basstler's reads its token from.
    """

    TOKEN = "ANOTHER_JOB_TOKEN"
    """
    The token the other job starts a workflow with.
    """


def shared_use(owner: str) -> TokenUse:
    """
    :param owner: The owner of the repository the other job reaches.
    :return: Another job of basstler's, starting a workflow there.
    """
    return TokenUse(
        "starts a build",
        (Repository(owner, "site"),),
        {RepositoryPermission.ACTIONS: PermissionLevel.WRITE},
        AnotherJobSecret.TOKEN,
        (FORK,),
    )


def test_a_job_on_the_pull_requests_owner_shares_the_token():
    other = shared_use(UPSTREAM.owner)
    setup = MarkViewedSetup(FORK, shared_uses=(other,))
    setup.run(answers(SECRET=None))
    create, store = setup.user_steps
    assert (
        f"{RepositoryPermission.ACTIONS}={PermissionLevel.WRITE}"
        in create.browser_steps[0],
        store.command.count("gh secret set"),
    ) == (True, 2)


def test_a_job_on_another_owner_s_repositories_gets_a_token_of_its_own():
    setup = MarkViewedSetup(FORK, shared_uses=(shared_use("someone-else"),))
    setup.run(answers(SECRET=None))
    alone = setup.token_use(RepositoryDetails.from_json(fork_details()))
    assert [step.token.uses for step in setup.user_steps] == [(alone,), (alone,)]


def test_a_secret_that_may_be_stored_already_says_its_token_steps_may_be_skipped():
    client = answers()
    client.forbidden.add(Resource.SECRET)
    unread = MarkViewedSetup(FORK)
    unread.run(client)
    assert [
        (step.may_be_done, step.description.startswith(step.condition))
        for step in unread.user_steps
    ] == [(True, True), (True, True)]


def test_a_token_left_to_the_user_is_reported_as_left():
    setup = MarkViewedSetup(FORK)
    setup.run(answers(SECRET=None))
    assert setup.token_left


def test_a_stored_token_is_not_reported_as_left():
    setup = MarkViewedSetup(FORK)
    setup.run(answers())
    assert not setup.token_left


# %% a pull request already carrying the workflow, or one that cannot be opened


HEAD_COMMIT = "a-head-commit"
"""
The commit another pull request's branch points at.
"""


def carrying_pull_request(base: str) -> dict[str, Any]:
    """
    :param base: The branch it merges into.
    :return: An open pull request from another branch, as the listing gives it.
    """
    return {
        "number": 9,
        "title": "Another pull request",
        "html_url": FORK.pull_request_url(9),
        "state": "open",
        "merged_at": None,
        "head": {
            "ref": "another-branch",
            "sha": HEAD_COMMIT,
            "user": {"login": FORK.owner},
        },
        "base": {"ref": base, "sha": BASE_COMMIT},
    }


def carried_workflow(
    setup: MarkViewedSetup, base: str, text: str
) -> PathAnsweringClient:
    """
    :param setup: The setup whose workflow another pull request holds.
    :param base: The branch that pull request merges into.
    :param text: The workflow file its head holds.
    :return: A repository that is no fork, with that pull request open.
    """
    client = unforked_answers()
    proposal = setup.workflow_proposal(
        RepositoryDetails.from_json(fork_details(is_fork=False))
    )
    client.answers[proposal.open_pull_requests_path] = [carrying_pull_request(base)]
    client.answers[FORK.contents_path(WORKFLOW_FILE_PATH, HEAD_COMMIT)] = {
        "sha": INSTALLED_BLOB,
        "content": base64.encodebytes(text.encode()).decode(),
    }
    return client


def test_an_open_pull_request_carrying_the_workflow_is_reported_and_nothing_written():
    setup = MarkViewedSetup(FORK)
    client = carried_workflow(
        setup, STAND_IN_DEFAULT_BRANCH.name, setup.caller_workflow
    )
    setup.run(client)
    assert (client.sent, setup.user_steps[0].browser_steps[0]) == (
        [],
        f"Open {carrying_pull_request('')['html_url']}.",
    )


def test_a_pull_request_carrying_another_version_is_not_taken_for_it():
    setup = MarkViewedSetup(FORK)
    client = carried_workflow(setup, STAND_IN_DEFAULT_BRANCH.name, "another workflow\n")
    setup.run(client)
    assert len(sent_of(client, NewPullRequest)) == 1


def test_a_carrying_pull_request_on_another_base_says_what_it_merges_into():
    setup = MarkViewedSetup(FORK)
    client = carried_workflow(setup, "a-stacked-base", setup.caller_workflow)
    setup.run(client)
    installed = f"the {WorkflowLocation.MARK_VIEWED.name} workflow on"
    (reason,) = [
        step.reason for step in setup.steps if step.description.startswith(installed)
    ]
    assert "merging into a-stacked-base" in reason


def test_a_refused_pull_request_gets_the_form_with_everything_filled_in():
    client = unforked_answers()
    client.refused_writes.add(FORK.pull_requests_path)
    setup = MarkViewedSetup(FORK)
    setup.run(client)
    proposal = setup.workflow_proposal(
        RepositoryDetails.from_json(fork_details(is_fork=False))
    )
    assert (
        setup.user_steps[0]
        .browser_steps[0]
        .startswith(f"Open {proposal.form.link.url} ")
    )


def test_of_two_stacked_pull_requests_carrying_the_workflow_the_lower_is_reported():
    setup = MarkViewedSetup(FORK)
    client = carried_workflow(setup, "a-stacked-base", setup.caller_workflow)
    lower = carrying_pull_request("a-stacked-base")
    upper = dict(
        carrying_pull_request(lower["head"]["ref"]),
        number=10,
        html_url=FORK.pull_request_url(10),
        head=dict(lower["head"], ref="an-upper-branch"),
    )
    proposal = setup.workflow_proposal(
        RepositoryDetails.from_json(fork_details(is_fork=False))
    )
    client.answers[proposal.open_pull_requests_path] = [upper, lower]
    setup.run(client)
    assert setup.user_steps[0].browser_steps[0] == f"Open {lower['html_url']}."
