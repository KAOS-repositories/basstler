"""
Tests for basstler.plan.session_record and basstler.plan.session_close_command: what a
session did that the plans do not say yet, and the stop it refuses meanwhile.
"""

from __future__ import annotations

import io
import json
from enum import StrEnum

import pytest

from basstler.locations import PluginLocation, ProjectLocation
from basstler.plan.session_close_command import (
    RefusedStop,
    ReportedDecision,
    StopRequest,
    record_decision,
    stop_answer,
)
from basstler.plan.session_record import (
    DEFAULT_BRANCH_REFERENCE,
    BranchWithoutItem,
    Decision,
    ItemBehindBranch,
    SessionClose,
    SessionCloseCommandName,
    SessionRecord,
    UnrecordedDecisions,
)
from basstler.shell_configuration import FetchedBranchReference

from ..constants.notes import ScratchBranch
from ..constants.paths import DatasetLocation, RepositoryLocation
from ..scratch_repository import ScratchRepository

# %% the clone

PLAN_ID = "example-plan"
"""
The plan whose item owns the scratch repository's work branch.
"""

UNTRACKED_BRANCH = "work-no-item-owns"
"""
A branch no plan item owns.
"""


class HookInput(StrEnum):
    """
    The recorded hook inputs, by what happened.
    """

    STOPPING = "stop-hook-input.json"
    """
    A session about to stop.
    """

    STOPPING_AFTER_A_REFUSAL = "stop-hook-input-continuing.json"
    """
    A session about to stop after a refused stop made it continue.
    """

    QUESTION_ANSWERED = "answered-question-input.json"
    """
    The user answered a question.
    """

    PLAN_APPROVED = "approved-plan-input.json"
    """
    The user approved a plan.
    """

    @property
    def text(self) -> str:
        """
        :return: The recorded input.
        """
        return (DatasetLocation.SESSION_CLOSE / self).read_text()


@pytest.fixture
def default_branch(scratch_repository: ScratchRepository) -> str:
    """
    :return: The default branch of a scratch repository that holds one commit on it,
        knows it as its default, and has a work branch one plan item owns checked out.
    """
    scratch_repository.write("README.md", "scratch repo\n")
    scratch_repository.commit_everything("initial commit")
    branch = scratch_repository.git.checked_out_branch()
    scratch_repository.run_git(
        "symbolic-ref", DEFAULT_BRANCH_REFERENCE, f"refs/heads/{branch}"
    )
    scratch_repository.publish_notes_branch(
        {ProjectLocation.PLAN_BRANCH_INDEX: f"{ScratchBranch.WORK}\t{PLAN_ID}\n"}
    )
    scratch_repository.run_git(
        "update-ref",
        FetchedBranchReference.PERSONAL_NOTES,
        f"refs/heads/{ScratchBranch.PERSONAL_NOTES}",
    )
    return branch


@pytest.fixture
def close(scratch_repository: ScratchRepository, default_branch: str) -> SessionClose:
    """
    :return: The close of a session that began in the scratch repository.
    """
    SessionClose.in_checkout(scratch_repository.git).begin()
    return SessionClose.in_checkout(scratch_repository.git)


def commit_more(repository: ScratchRepository) -> SessionClose:
    """
    Add a commit to the checked-out branch.

    :param repository: The clone.
    :return: The session's close, reading the clone as it is now.
    """
    repository.write("more.txt", repository.git.commit_at("HEAD"))
    repository.commit_everything("more work")
    return SessionClose.in_checkout(repository.git)


# %% what is unrecorded


class TestABranchItsItemIsBehind:
    """
    A branch an item owns is unrecorded once it moves past the last settled commit.
    """

    def test_a_session_that_did_nothing_has_nothing_to_record(
        self, close: SessionClose
    ):
        assert close.unrecorded_work == []

    def test_a_clone_no_session_began_a_record_in_is_not_judged(
        self, scratch_repository: ScratchRepository, default_branch: str
    ):
        assert commit_more(scratch_repository).unrecorded_work == []

    def test_a_commit_leaves_the_item_behind_its_branch(
        self, scratch_repository: ScratchRepository, close: SessionClose
    ):
        assert commit_more(scratch_repository).unrecorded_work == [
            ItemBehindBranch(ScratchBranch.WORK, PLAN_ID)
        ]

    def test_a_plan_save_settles_it(
        self, scratch_repository: ScratchRepository, close: SessionClose
    ):
        moved = commit_more(scratch_repository)
        moved.settle()
        assert moved.unrecorded_work == []

    def test_the_session_s_word_settles_it(
        self, scratch_repository: ScratchRepository, close: SessionClose
    ):
        moved = commit_more(scratch_repository)
        moved.confirm()
        assert moved.unrecorded_work == []

    def test_beginning_again_keeps_the_record(
        self, scratch_repository: ScratchRepository, close: SessionClose
    ):
        """
        A resumed session does not forget what the one before left unrecorded.
        """
        moved = commit_more(scratch_repository)
        moved.begin()
        assert moved.unrecorded_work == [ItemBehindBranch(ScratchBranch.WORK, PLAN_ID)]


class TestABranchNoItemOwns:
    """
    A branch with commits and no item stays unrecorded until it gets one or is confirmed
    untracked.
    """

    @pytest.fixture
    def untracked(
        self, scratch_repository: ScratchRepository, close: SessionClose
    ) -> SessionClose:
        """
        :return: The session's close with a branch no item owns checked out.
        """
        scratch_repository.run_git("checkout", "--quiet", "-b", UNTRACKED_BRANCH)
        return SessionClose.in_checkout(scratch_repository.git)

    def test_it_is_unrecorded(self, untracked: SessionClose):
        assert untracked.unrecorded_work == [BranchWithoutItem(UNTRACKED_BRANCH)]

    def test_a_plan_save_does_not_settle_it(self, untracked: SessionClose):
        untracked.settle()
        assert untracked.unrecorded_work == [BranchWithoutItem(UNTRACKED_BRANCH)]

    def test_the_session_s_word_settles_it_for_later_commits_too(
        self, scratch_repository: ScratchRepository, untracked: SessionClose
    ):
        untracked.confirm()
        assert commit_more(scratch_repository).unrecorded_work == []

    def test_the_default_branch_is_never_unrecorded(
        self,
        scratch_repository: ScratchRepository,
        close: SessionClose,
        default_branch: str,
    ):
        scratch_repository.run_git("checkout", "--quiet", default_branch)
        assert SessionClose.in_checkout(scratch_repository.git).unrecorded_work == []


class TestADecisionOfTheUser:
    """
    A decision stays unrecorded until a plan is saved or the session says it changes
    none.
    """

    def test_it_is_unrecorded(self, close: SessionClose):
        close.record_decision(Decision.QUESTION_ANSWERED)
        close.record_decision(Decision.PLAN_APPROVED)
        assert close.unrecorded_work == [
            UnrecordedDecisions((Decision.QUESTION_ANSWERED, Decision.PLAN_APPROVED))
        ]

    def test_a_plan_save_settles_it(self, close: SessionClose):
        close.record_decision(Decision.QUESTION_ANSWERED)
        close.settle()
        assert close.unrecorded_work == []

    @pytest.mark.parametrize(
        ("hook_input", "decision"),
        [
            (HookInput.QUESTION_ANSWERED, Decision.QUESTION_ANSWERED),
            (HookInput.PLAN_APPROVED, Decision.PLAN_APPROVED),
        ],
    )
    def test_the_hook_input_names_the_decision(
        self, hook_input: HookInput, decision: Decision
    ):
        reported = ReportedDecision.from_json(json.loads(hook_input.text))
        assert reported.tool_name is decision

    def test_the_command_records_the_decision_on_its_input(
        self,
        scratch_repository: ScratchRepository,
        close: SessionClose,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.chdir(scratch_repository.project_root)
        monkeypatch.setattr("sys.stdin", io.StringIO(HookInput.PLAN_APPROVED.text))
        record_decision()
        assert close.store.read() == SessionRecord(
            settled_commit=close.work.commit,
            unrecorded_decisions=(Decision.PLAN_APPROVED,),
        )


# %% the stop


class TestStoppingTheSession:
    """
    A stop is refused once while something is unrecorded.
    """

    def test_a_session_with_nothing_unrecorded_may_stop(self, close: SessionClose):
        request = StopRequest.from_json(json.loads(HookInput.STOPPING.text))
        assert stop_answer(request, close) is None

    def test_a_stop_is_refused_naming_everything_unrecorded(
        self, scratch_repository: ScratchRepository, close: SessionClose
    ):
        close.record_decision(Decision.QUESTION_ANSWERED)
        moved = commit_more(scratch_repository)
        request = StopRequest.from_json(json.loads(HookInput.STOPPING.text))
        answer = stop_answer(request, moved)
        assert isinstance(answer, RefusedStop)
        assert [line.removeprefix("- ") for line in answer.reason.splitlines()[1:]] == [
            work.description for work in moved.unrecorded_work
        ]

    def test_a_refused_stop_is_not_refused_twice(
        self, scratch_repository: ScratchRepository, close: SessionClose
    ):
        moved = commit_more(scratch_repository)
        request = StopRequest.from_json(
            json.loads(HookInput.STOPPING_AFTER_A_REFUSAL.text)
        )
        assert stop_answer(request, moved) is None

    @pytest.mark.parametrize(
        "work",
        [
            UnrecordedDecisions((Decision.QUESTION_ANSWERED,)),
            BranchWithoutItem(UNTRACKED_BRANCH),
            ItemBehindBranch(ScratchBranch.WORK, PLAN_ID),
        ],
    )
    def test_everything_unrecorded_names_the_command_that_settles_it(self, work):
        assert SessionCloseCommandName.CONFIRM.invocation() in work.description


# %% the hooks


def hook_commands(event: str) -> list[str]:
    """
    :param event: A Claude Code hook event.
    :return: The commands the plugin registers for it.
    """
    registered = json.loads((RepositoryLocation.HOOKS / "hooks.json").read_text())[
        "hooks"
    ]
    return [hook["command"] for entry in registered[event] for hook in entry["hooks"]]


def hook_command_running(command: SessionCloseCommandName) -> str:
    """
    :param command: A ``session-close`` command.
    :return: The hook command that runs it through the plugin's entry point.
    """
    return (
        f"${{CLAUDE_PLUGIN_ROOT}}/{PluginLocation.ENTRY_POINT_SCRIPT.as_posix()} "
        f"__main__ {SessionCloseCommandName.GROUP} {command}"
    )


class TestThePluginsHooks:
    """
    The plugin registers the commands for the events they answer.
    """

    def test_a_stop_asks_the_stop_command(self):
        assert hook_commands("Stop") == [
            hook_command_running(SessionCloseCommandName.STOP_HOOK)
        ]

    def test_a_decision_is_recorded_after_the_tools_that_carry_one(self):
        registered = json.loads((RepositoryLocation.HOOKS / "hooks.json").read_text())[
            "hooks"
        ]["PostToolUse"]
        assert [entry["matcher"] for entry in registered] == ["|".join(Decision)]
        assert hook_commands("PostToolUse") == [
            hook_command_running(SessionCloseCommandName.DECISION)
        ]
