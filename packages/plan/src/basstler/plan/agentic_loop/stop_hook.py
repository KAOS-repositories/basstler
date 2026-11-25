"""
The hook Claude Code runs when a turn ends: it starts the session a finished stage of an
agentic loop asked for.

Usage:
    "${BASSTLER_PYTHON}" -m basstler.plan.agentic_loop.stop_hook
"""

from __future__ import annotations

import os
from pathlib import Path

from cyclopts import App

from basstler.exit_codes import StackExitCode
from basstler.git.commands import GitCommandRunner
from basstler.locations import ClaudeCodeVariable
from basstler.plan.agentic_loop.session_start import SessionStarter
from basstler.plan.agentic_loop.stage import PendingSession

app = App(help=__doc__)
"""
The command, run with the project root as its working directory.
"""


@app.default
def start_pending_session() -> StackExitCode:
    """
    Start the session the turn's finished stage recorded, if it recorded one.

    :return: :attr:`StackExitCode.SUCCESS`; a failure to start raises instead.
    """
    git = GitCommandRunner(
        Path(os.environ.get(ClaudeCodeVariable.PROJECT_DIRECTORY, Path.cwd()))
    )
    session = PendingSession(git).take()
    if session is not None:
        SessionStarter.for_this_machine(git).start(session)
    return StackExitCode.SUCCESS


if __name__ == "__main__":
    app()
