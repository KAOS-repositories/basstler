"""
The ``basstler session-close`` commands: keeping a clone's session record, and refusing
a session's stop while the plans do not say what it did.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from cyclopts import App

from basstler.exit_codes import ExitCode
from basstler.git.commands import GitCommandRunner
from basstler.json_model import ValidatedJSONModel
from basstler.plan.session_record import (
    Decision,
    SessionClose,
    SessionCloseCommandName,
)
from basstler.standard_streams import StandardStreamHandler

logger = StandardStreamHandler.logger_for(__name__)
"""
This module's logger, which is also what its commands print through.
"""

# %% what Claude Code sends and reads


class ReportedDecision(ValidatedJSONModel):
    """
    The hook input Claude Code sends after a tool call through which the user decided
    something.
    """

    tool_name: Decision
    """
    What the user decided.
    """


class StopRequest(ValidatedJSONModel):
    """
    The hook input Claude Code sends when a session is about to stop.
    """

    stop_hook_active: bool = False
    """
    Whether the session is already continuing because a stop was refused.
    """


class RefusedStop(ValidatedJSONModel):
    """
    The answer that makes Claude Code continue the session instead of stopping it.
    """

    reason: str
    """
    What the session is told to do before it stops.
    """

    decision: str = "block"
    """
    The word Claude Code reads a refusal from.
    """


# %% the commands


class SessionCloseExitCode(ExitCode):
    """
    What a ``basstler session-close`` command's exit status tells its caller.
    """

    SUCCESS = 0
    """
    The command did what it was asked, and the plans say what the session did.
    """

    UNRECORDED_WORK = 1
    """
    The session did something the plans do not say yet.
    """


session_close_app = App(
    name=SessionCloseCommandName.GROUP,
    help="Keep what a session settled with the plans, and say what it has not.",
)
"""
The ``session-close`` command group.
"""


def session_close() -> SessionClose:
    """
    :return: The close of the session working in the current directory's clone.
    """
    return SessionClose.in_checkout(GitCommandRunner(Path.cwd()))


@session_close_app.command(name=SessionCloseCommandName.BEGIN)
def begin() -> SessionCloseExitCode:
    """
    Start the session record at the checked-out commit, unless the clone has one.
    """
    session_close().begin()
    return SessionCloseExitCode.SUCCESS


@session_close_app.command(name=SessionCloseCommandName.DECISION)
def record_decision() -> SessionCloseExitCode:
    """
    Record the decision whose hook input is on standard input.
    """
    reported = ReportedDecision.from_json(json.load(sys.stdin))
    session_close().record_decision(reported.tool_name)
    return SessionCloseExitCode.SUCCESS


@session_close_app.command(name=SessionCloseCommandName.SETTLE)
def settle() -> SessionCloseExitCode:
    """
    Record that a plan was saved at the checked-out commit.
    """
    session_close().settle()
    return SessionCloseExitCode.SUCCESS


@session_close_app.command(name=SessionCloseCommandName.CONFIRM)
def confirm() -> SessionCloseExitCode:
    """
    Record that the plans already say what is true, and that the checked-out branch, when
    no item owns it, is deliberately untracked.
    """
    session_close().confirm()
    return SessionCloseExitCode.SUCCESS


@session_close_app.command(name=SessionCloseCommandName.CHECK)
def check() -> SessionCloseExitCode:
    """
    Print what the session did that the plans do not say yet.
    """
    unrecorded = session_close().unrecorded_work
    for work in unrecorded:
        logger.info(work.description)
    if unrecorded:
        return SessionCloseExitCode.UNRECORDED_WORK
    logger.info("The plans say what this session did.")
    return SessionCloseExitCode.SUCCESS


def stop_answer(request: StopRequest, close: SessionClose) -> RefusedStop | None:
    """
    :param request: Claude Code's question.
    :param close: The close of the session asking.
    :return: The refusal, or ``None`` when the session may stop: nothing is unrecorded,
        or a stop was refused already and the session answered it.
    """
    unrecorded = close.unrecorded_work
    if request.stop_hook_active or not unrecorded:
        return None
    return RefusedStop(
        reason="Before stopping, record what this session did:\n"
        + "\n".join(f"- {work.description}" for work in unrecorded)
    )


@session_close_app.command(name=SessionCloseCommandName.STOP_HOOK)
def answer_stop_hook() -> SessionCloseExitCode:
    """
    Answer the stop request on standard input: refuse once while the plans do not say
    what the session did.
    """
    answer = stop_answer(StopRequest.from_json(json.load(sys.stdin)), session_close())
    if answer is not None:
        logger.info(json.dumps(answer.to_json()))
    return SessionCloseExitCode.SUCCESS
