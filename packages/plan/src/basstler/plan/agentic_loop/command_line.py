"""
The ``basstler agentic-loop`` commands: turning the loop on or off, and recording a
finished stage so the end of its turn starts the next one.
"""

from __future__ import annotations

import dataclasses
import json
import os
from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter

from basstler.exit_codes import StackExitCode
from basstler.git.commands import GitCommandRunner
from basstler.locations import ClaudeCodeVariable
from basstler.plan.agentic_loop.settings import LoopSettingsStore
from basstler.plan.agentic_loop.stage import (
    AgenticLoop,
    ChangesCompletion,
    LoopPullRequest,
    LoopStep,
    PendingSession,
    ReviewCompletion,
    StageCompletion,
)
from basstler.standard_streams import StandardStreamHandler

logger = StandardStreamHandler.logger_for(__name__)
"""
This module's logger, which is also what its commands print through.
"""

agentic_loop_app = App(
    name="agentic-loop",
    help="Turn the agentic loop on or off, and record the stages it finishes.",
)
"""
The ``agentic-loop`` command group.
"""

LoopRequest = Annotated[bool | None, Parameter(name="--loop", negative="--no-loop")]
"""
Whether this run asks for the loop on or off, overriding the user's setting.
"""

# %% the setting


def project_root() -> Path:
    """
    :return: The project the command acts on, as Claude Code names it, else the current
        directory.
    """
    return Path(os.environ.get(ClaudeCodeVariable.PROJECT_DIRECTORY, Path.cwd()))


@agentic_loop_app.command(name="show")
def show_settings() -> StackExitCode:
    """
    Print the user's loop setting as JSON.
    """
    settings = LoopSettingsStore.from_project_root(project_root()).read()
    logger.info(json.dumps(settings.to_json()))
    return StackExitCode.SUCCESS


@agentic_loop_app.command(name="turn-on")
def turn_on(*, rounds: int | None = None) -> StackExitCode:
    """
    Turn the loop on, and push the notes branch.

    :param rounds: The most reviews one pull request gets; unchanged when not given.
    """
    store = LoopSettingsStore.from_project_root(project_root())
    settings = store.read()
    store.write(
        dataclasses.replace(
            settings,
            enabled=True,
            maximum_review_rounds=(
                settings.maximum_review_rounds if rounds is None else rounds
            ),
        )
    )
    return show_settings()


@agentic_loop_app.command(name="turn-off")
def turn_off() -> StackExitCode:
    """
    Turn the loop off, and push the notes branch.
    """
    store = LoopSettingsStore.from_project_root(project_root())
    store.write(dataclasses.replace(store.read(), enabled=False))
    return show_settings()


# %% finished stages


def record_successor(completion: StageCompletion, requested: bool | None) -> None:
    """
    Record the session the loop starts after *completion*, and print what it does.

    :param completion: The stage that finished.
    :param requested: Whether the run asked for the loop on or off.
    """
    root = project_root()
    loop = AgenticLoop(LoopSettingsStore.from_project_root(root).read(), requested)
    step = LoopStep.from_successor(loop.successor(completion))
    if step.next_session is not None:
        PendingSession(GitCommandRunner(root)).record(step.next_session)
    logger.info(json.dumps(step.to_json()))


@agentic_loop_app.command(name="finish-changes")
def finish_changes(
    *, pull_request: int, review_round: int = 0, loop: LoopRequest = None
) -> StackExitCode:
    """
    Record that a kickoff or resolve pushed its changes, so the next review starts when
    the turn ends.

    :param pull_request: The pull request of the checked-out branch.
    :param review_round: The review the resolve addressed; ``0`` for a kickoff.
    :param loop: Turn the loop on or off for this run.
    """
    reference = LoopPullRequest.checked_out(
        GitCommandRunner(project_root()), pull_request
    )
    record_successor(ChangesCompletion(reference, review_round), loop)
    return StackExitCode.SUCCESS


@agentic_loop_app.command(name="finish-review")
def finish_review(
    *, pull_request: int, review_round: int, findings: int, loop: LoopRequest = None
) -> StackExitCode:
    """
    Record that a review posted its findings, so their resolve starts when the turn
    ends.

    :param pull_request: The pull request of the checked-out branch.
    :param review_round: The review that finished, counting from 1.
    :param findings: How many findings it posted.
    :param loop: Turn the loop on or off for this run.
    """
    reference = LoopPullRequest.checked_out(
        GitCommandRunner(project_root()), pull_request
    )
    record_successor(ReviewCompletion(reference, review_round, findings), loop)
    return StackExitCode.SUCCESS
