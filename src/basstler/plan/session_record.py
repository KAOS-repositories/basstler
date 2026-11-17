"""
What a session has done that the plans do not say yet, and the record of what it settled
with them.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from enum import StrEnum
from functools import cached_property

from basstler.git.commands import GitCommandRunner
from basstler.json_model import ValidatedJSONModel
from basstler.locations import PluginLocation, ProjectLocation, RepositoryStateLocation
from basstler.shell_configuration import FetchedBranchReference

DEFAULT_BRANCH_REFERENCE = "refs/remotes/origin/HEAD"
"""
Where git keeps which branch of ``origin`` is its default.
"""

# %% the commands


class SessionCloseCommandName(StrEnum):
    """
    The ``basstler session-close`` commands, named once for the command tree, the hooks
    and every message that tells a session to run one.
    """

    GROUP = "session-close"
    """
    The command group.
    """

    BEGIN = "begin"
    """
    Starts the record at the checked-out commit, unless the clone already has one.
    """

    DECISION = "decision"
    """
    Records a decision the user made, from the hook input Claude Code reports it with.
    """

    SETTLE = "settle"
    """
    Records that a plan was saved at the checked-out commit.
    """

    CONFIRM = "confirm"
    """
    Records the session's word that the plans already say what is true.
    """

    CHECK = "check"
    """
    Prints what the plans do not say yet.
    """

    STOP_HOOK = "stop-hook"
    """
    Answers Claude Code's question whether the session may stop.
    """

    def invocation(self) -> str:
        """
        :return: The whole command as a person types it.
        """
        return " ".join(("basstler", SessionCloseCommandName.GROUP, self))


# %% the record


class Decision(StrEnum):
    """
    A decision the user made in a session, valued as the tool Claude Code reports it
    through.
    """

    QUESTION_ANSWERED = "AskUserQuestion"
    """
    The user answered a question the session put.
    """

    PLAN_APPROVED = "ExitPlanMode"
    """
    The user approved a plan the session presented.
    """


class SessionRecord(ValidatedJSONModel):
    """
    What the sessions in one clone last settled with the plans, and what happened since.
    """

    settled_commit: str | None = None
    """
    The checked-out commit when a plan was last saved or confirmed current.
    """

    unrecorded_decisions: tuple[Decision, ...] = ()
    """
    The decisions the user made since then.
    """

    branches_without_item: tuple[str, ...] = ()
    """
    The branches confirmed as work no plan item tracks.
    """


@dataclass(frozen=True)
class SessionRecordStore:
    """
    Keeps one clone's :class:`SessionRecord` in its git directory.
    """

    git: GitCommandRunner
    """
    The clone.
    """

    def read(self) -> SessionRecord | None:
        """
        :return: The clone's record, or ``None`` when no session began one.
        """
        path = self.git.repository_state_path(RepositoryStateLocation.SESSION_RECORD)
        if not path.exists():
            return None
        return SessionRecord.from_json(json.loads(path.read_text()))

    def write(self, record: SessionRecord) -> None:
        """
        :param record: The record to keep in place of the clone's.
        """
        path = self.git.repository_state_path(RepositoryStateLocation.SESSION_RECORD)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record.to_json(), indent=2) + "\n")


# %% the checked-out work


@dataclass(frozen=True)
class CheckedOutWork:
    """
    The branch a clone has checked out, as the plans it last fetched see it.
    """

    git: GitCommandRunner
    """
    The clone.
    """

    @cached_property
    def branch(self) -> str:
        """
        The checked-out branch's name.
        """
        return self.git.checked_out_branch()

    @cached_property
    def commit(self) -> str:
        """
        The checked-out commit.
        """
        return self.git.commit_at("HEAD")

    @cached_property
    def has_commits_of_its_own(self) -> bool:
        """
        Whether the branch holds a commit the default branch does not, which it is taken
        to when the clone does not know the default branch.
        """
        default_branch = self.git.attempt(
            "symbolic-ref", "--quiet", DEFAULT_BRANCH_REFERENCE
        )
        if not default_branch.succeeded:
            return True
        ahead = self.git.run("rev-list", "--count", f"{default_branch.output}..HEAD")
        return ahead != "0"

    @cached_property
    def plan_identifier(self) -> str | None:
        """
        The plan whose item owns the branch, or ``None`` when no item does.
        """
        index = self.git.attempt(
            "show",
            FetchedBranchReference.PERSONAL_NOTES.file_at(
                ProjectLocation.PLAN_BRANCH_INDEX
            ),
        )
        plan_of_branch = dict(
            line.split("\t", 1) for line in index.output.splitlines() if "\t" in line
        )
        return plan_of_branch.get(self.branch)


# %% what the plans do not say yet


class UnrecordedWork(ABC):
    """
    One thing a session did that the plans do not say yet.
    """

    @property
    @abstractmethod
    def description(self) -> str:
        """
        What is unrecorded, and the command that records it.
        """


@dataclass(frozen=True)
class UnrecordedDecisions(UnrecordedWork):
    """
    The user decided something after the plans were last saved.
    """

    decisions: tuple[Decision, ...]
    """
    What the user decided, in order.
    """

    @property
    def description(self) -> str:
        answered = self.decisions.count(Decision.QUESTION_ANSWERED)
        approved = self.decisions.count(Decision.PLAN_APPROVED)
        return (
            f"The user answered {answered} question(s) and approved {approved} plan(s) "
            "since a plan was last saved. Write what that changes into plan.yaml and "
            f"save it with {PluginLocation.PLAN_SAVING_SCRIPT.name}; if it changes no "
            f"plan, run `{SessionCloseCommandName.CONFIRM.invocation()}`."
        )


@dataclass(frozen=True)
class BranchWithoutItem(UnrecordedWork):
    """
    The checked-out branch holds commits and no plan item owns it.
    """

    branch: str
    """
    The branch.
    """

    @property
    def description(self) -> str:
        return (
            f"Branch {self.branch} holds commits and no plan item owns it. Run "
            "/add-plan-item to decide where the work belongs; if it is deliberately "
            f"untracked, run `{SessionCloseCommandName.CONFIRM.invocation()}`."
        )


@dataclass(frozen=True)
class ItemBehindBranch(UnrecordedWork):
    """
    The checked-out branch moved after its plan was last saved.
    """

    branch: str
    """
    The branch.
    """

    plan_identifier: str
    """
    The plan whose item owns it.
    """

    @property
    def description(self) -> str:
        return (
            f"Branch {self.branch} moved since plan {self.plan_identifier} was last "
            "saved. Bring its item's status, pull request and notes up to date and save "
            f"with {PluginLocation.PLAN_SAVING_SCRIPT.name} {self.plan_identifier}; if "
            "the item already says what is true, run "
            f"`{SessionCloseCommandName.CONFIRM.invocation()}`."
        )


# %% the session's close


@dataclass(frozen=True)
class SessionClose:
    """
    Decides what a clone's session still has to record before it stops, and records
    what it settles.
    """

    store: SessionRecordStore
    """
    Where the clone's record is kept.
    """

    work: CheckedOutWork
    """
    What the clone has checked out.
    """

    @classmethod
    def in_checkout(cls, git: GitCommandRunner) -> SessionClose:
        """
        :param git: The clone.
        :return: The close of the session working in it.
        """
        return cls(SessionRecordStore(git), CheckedOutWork(git))

    @property
    def unrecorded_work(self) -> list[UnrecordedWork]:
        """
        Everything the plans do not say yet; empty when no session began a record.
        """
        record = self.store.read()
        if record is None:
            return []
        unrecorded: list[UnrecordedWork] = []
        if record.unrecorded_decisions:
            unrecorded.append(UnrecordedDecisions(record.unrecorded_decisions))
        if not self.work.has_commits_of_its_own:
            return unrecorded
        if self.work.plan_identifier is None:
            if self.work.branch not in record.branches_without_item:
                unrecorded.append(BranchWithoutItem(self.work.branch))
        elif self.work.commit != record.settled_commit:
            unrecorded.append(
                ItemBehindBranch(self.work.branch, self.work.plan_identifier)
            )
        return unrecorded

    @property
    def record(self) -> SessionRecord:
        """
        The clone's record, empty when no session began one.
        """
        return self.store.read() or SessionRecord()

    def begin(self) -> None:
        """
        Start the record at the checked-out commit, unless the clone already has one.
        """
        if self.store.read() is None:
            self.store.write(SessionRecord(settled_commit=self.work.commit))

    def record_decision(self, decision: Decision) -> None:
        """
        :param decision: What the user just decided.
        """
        record = self.record
        self.store.write(
            replace(
                record,
                unrecorded_decisions=(*record.unrecorded_decisions, decision),
            )
        )

    def settle(self) -> None:
        """
        Record that the plans were saved with the checked-out commit and every decision
        so far in view.
        """
        self.store.write(
            replace(
                self.record, settled_commit=self.work.commit, unrecorded_decisions=()
            )
        )

    def confirm(self) -> None:
        """
        Record the session's word that the plans say what is true: :meth:`settle`, and
        the checked-out branch, when no item owns it, as deliberately untracked.
        """
        self.settle()
        if self.work.plan_identifier is not None:
            return
        record = self.record
        self.store.write(
            replace(
                record,
                branches_without_item=tuple(
                    sorted({*record.branches_without_item, self.work.branch})
                ),
            )
        )
