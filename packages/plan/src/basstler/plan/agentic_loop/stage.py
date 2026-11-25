"""
The stages of an agentic loop, and which session a finished stage starts next.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from basstler.class_property import classproperty
from basstler.git.commands import GitCommandRunner
from basstler.github.repository import PullRequestReference, Repository
from basstler.json_model import ValidatedJSONModel
from basstler.locations import AgenticLoopLocation, RepositoryStateLocation
from basstler.plan.agentic_loop.settings import LoopSettings
from basstler.plan.skills import PlanItemResolveSkill, PlanItemReviewSkill
from basstler.playbook.skill import Skill
from basstler.render_common import TemplatePage
from basstler.text_file import TextFile

# %% the stages a loop starts sessions for


class LoopStage(StrEnum):
    """
    A stage of the loop that runs in a session of its own.
    """

    REVIEW = "review"
    """
    The pull request is reviewed, and every finding posted on it.
    """

    RESOLVE = "resolve"
    """
    The findings of the last review are addressed.
    """

    @property
    def skill(self) -> Skill:
        """
        The skill a session of this stage runs.
        """
        match self:
            case LoopStage.REVIEW:
                return PlanItemReviewSkill()
            case LoopStage.RESOLVE:
                return PlanItemResolveSkill()


class LoopEnd(StrEnum):
    """
    Why a finished stage starts no further session.
    """

    TURNED_OFF = "turned_off"
    """
    The loop is not on for this run.
    """

    NOTHING_FOUND = "nothing_found"
    """
    The last review posted no finding.
    """

    ROUNDS_USED_UP = "rounds_used_up"
    """
    The pull request had :attr:`LoopSettings.maximum_review_rounds` reviews.
    """


# %% the next session


class NextSession(ValidatedJSONModel):
    """
    A session the loop starts on one pull request.
    """

    stage: LoopStage
    """
    The stage the session runs.
    """

    repository: Repository
    """
    The repository the pull request is opened on.
    """

    branch: str
    """
    The name of the pull request's head branch, which the session checks out.
    """

    pull_request: int
    """
    The pull request's number.
    """

    review_round: int
    """
    The review the session runs, or resolves, counting from 1.
    """

    @property
    def title(self) -> str:
        """
        The session's title in the user's session list.
        """
        return f"{self.stage.skill.skill_name} #{self.pull_request}"

    @property
    def prompt(self) -> str:
        """
        The session's first message, which invokes its stage's skill.
        """
        return NextSessionPrompt(self).render()


@dataclass(frozen=True)
class NextSessionPrompt(TemplatePage):
    """
    The first message of a session the loop starts.
    """

    session: NextSession
    """
    The session it starts.
    """

    @classproperty
    def template(cls) -> str:
        return AgenticLoopLocation.PROMPT_TEMPLATE.name

    def render(self) -> str:
        """
        :return: The message, on one line.
        """
        return self.render_template(session=self.session).strip()


# %% finished stages


@dataclass(frozen=True)
class LoopPullRequest(PullRequestReference):
    """
    A pull request a loop works on, with the branch its sessions check out.
    """

    branch: str
    """
    The name of the pull request's head branch.
    """

    @classmethod
    def checked_out(cls, git: GitCommandRunner, number: int) -> LoopPullRequest:
        """
        :param git: A checkout of the pull request's head branch.
        :param number: The pull request's number.
        :return: The pull request, on the repository ``origin`` points at.
        """
        return cls(
            Repository.from_configured_remote(git),
            number,
            git.checked_out_branch(),
        )


@dataclass(frozen=True)
class StageCompletion(ABC):
    """
    A stage that finished on one pull request.
    """

    pull_request: LoopPullRequest
    """
    The pull request the stage worked on.
    """

    review_round: int
    """
    The review the stage belongs to: ``0`` before the first one.
    """

    @abstractmethod
    def successor(self, maximum_review_rounds: int) -> NextSession | LoopEnd:
        """
        :param maximum_review_rounds: The most reviews the pull request gets.
        :return: The session the loop starts next, or why it starts none.
        """

    def next_session(self, stage: LoopStage, review_round: int) -> NextSession:
        """
        :param stage: The stage the next session runs.
        :param review_round: The review it runs or resolves.
        :return: That session, on this stage's pull request.
        """
        return NextSession(
            stage=stage,
            repository=self.pull_request.repository,
            branch=self.pull_request.branch,
            pull_request=self.pull_request.number,
            review_round=review_round,
        )


@dataclass(frozen=True)
class ChangesCompletion(StageCompletion):
    """
    A kickoff or a resolve that pushed changes to the pull request, which the next
    review reads.
    """

    def successor(self, maximum_review_rounds: int) -> NextSession | LoopEnd:
        if self.review_round >= maximum_review_rounds:
            return LoopEnd.ROUNDS_USED_UP
        return self.next_session(LoopStage.REVIEW, self.review_round + 1)


@dataclass(frozen=True)
class ReviewCompletion(StageCompletion):
    """
    A review that posted its findings on the pull request.
    """

    findings: int
    """
    How many findings the review posted.
    """

    def successor(self, maximum_review_rounds: int) -> NextSession | LoopEnd:
        if self.findings == 0:
            return LoopEnd.NOTHING_FOUND
        return self.next_session(LoopStage.RESOLVE, self.review_round)


# %% the loop


class LoopStep(ValidatedJSONModel):
    """
    What the loop does after a finished stage, as the stage's command prints it.
    """

    next_session: NextSession | None = None
    """
    The session that starts when the turn ends, ``None`` when none does.
    """

    loop_end: LoopEnd | None = None
    """
    Why no session starts, ``None`` when one does.
    """

    @classmethod
    def from_successor(cls, successor: NextSession | LoopEnd) -> LoopStep:
        """
        :param successor: What the loop starts next, or why it starts nothing.
        :return: The step it stands for.
        """
        if isinstance(successor, LoopEnd):
            return cls(loop_end=successor)
        return cls(next_session=successor)


@dataclass(frozen=True)
class AgenticLoop:
    """
    The loop as one run sees it: the user's setting, and what the run asked for.
    """

    settings: LoopSettings
    """
    The user's setting.
    """

    requested: bool | None = None
    """
    Whether this run asked for the loop on or off, overriding the setting; ``None``
    when it asked for neither.
    """

    @property
    def enabled(self) -> bool:
        """
        Whether a finished stage starts the next stage's session in this run.
        """
        return self.settings.enabled if self.requested is None else self.requested

    def successor(self, completion: StageCompletion) -> NextSession | LoopEnd:
        """
        :param completion: The stage that finished.
        :return: The session the loop starts next, or why it starts none.
        """
        if not self.enabled:
            return LoopEnd.TURNED_OFF
        return completion.successor(self.settings.maximum_review_rounds)


# %% the session waiting for the turn's end


@dataclass(frozen=True)
class PendingSession:
    """
    The session a finished stage asks the end of its turn to start, kept per repository.
    """

    git: GitCommandRunner
    """
    The checkout the finished stage ran in.
    """

    @property
    def path(self) -> Path:
        """
        The file the session is recorded in until it is started.
        """
        return self.git.repository_state_path(
            RepositoryStateLocation.AGENTIC_LOOP_NEXT_SESSION
        )

    def record(self, session: NextSession) -> None:
        """
        :param session: The session to start when the turn ends.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        TextFile(self.path).write(json.dumps(session.to_json()))

    def take(self) -> NextSession | None:
        """
        :return: The recorded session, which is no longer recorded afterwards; ``None``
            when none is.
        """
        if not self.path.exists():
            return None
        session = NextSession.from_json(json.loads(TextFile(self.path).read()))
        self.path.unlink()
        return session
