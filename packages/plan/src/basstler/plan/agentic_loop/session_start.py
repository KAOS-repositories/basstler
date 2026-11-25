"""
Starting the session an agentic loop runs next: in the cloud by the finished session
itself, on a computer as a Claude Code process of its own.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from basstler.class_property import classproperty
from basstler.git.commands import GitCommandRunner
from basstler.json_model import ValidatedJSONModel
from basstler.locations import (
    AgenticLoopLocation,
    ClaudeCodeVariable,
    RepositoryStateLocation,
)
from basstler.plan.agentic_loop.exceptions import ClaudeCodeMissingError
from basstler.plan.agentic_loop.stage import NextSession
from basstler.render_common import TemplatePage
from basstler.session_tool import CloudSessionTool

# %% starting a session


class SessionStarter(ABC):
    """
    Starts the session an agentic loop runs next, when a turn ends.
    """

    @abstractmethod
    def start(self, session: NextSession) -> None:
        """
        :param session: The session to start.
        """

    @staticmethod
    def for_this_machine(git: GitCommandRunner) -> SessionStarter:
        """
        :param git: The checkout the finished session ran in.
        :return: The starter for a cloud session when this one is, else the one for a
            process on this computer.
        """
        if ClaudeCodeVariable.REMOTE.is_true():
            return CloudSessionStarter()
        return LocalSessionStarter(git)


# %% in the cloud


class StopDecision(StrEnum):
    """
    What a Stop hook decides about the turn ending.
    """

    BLOCK = "block"
    """
    The turn goes on, with the hook's reason as the next instruction.
    """


class StopHookAnswer(ValidatedJSONModel):
    """
    What a Stop hook prints to keep the turn going.
    """

    reason: str
    """
    What the session is told to do before it ends its turn.
    """

    decision: Literal[StopDecision.BLOCK] = StopDecision.BLOCK
    """
    The turn goes on.
    """


@dataclass(frozen=True)
class CloudSessionRequest(TemplatePage):
    """
    What a cloud session is told to do to start the loop's next session.
    """

    session: NextSession
    """
    The session to start.
    """

    @classproperty
    def template(cls) -> str:
        return AgenticLoopLocation.CLOUD_REQUEST_TEMPLATE.name

    def render(self) -> str:
        """
        :return: The instruction, in Markdown.
        """
        return self.render_template(
            session=self.session, create_session_tool=CloudSessionTool.CREATE_SESSION
        )


class CloudSessionStarter(SessionStarter):
    """
    Keeps the finished cloud session's turn going, to start the next session itself: a
    hook cannot call the cloud's session tools.
    """

    def start(self, session: NextSession) -> None:
        answer = StopHookAnswer(reason=CloudSessionRequest(session).render())
        sys.stdout.write(json.dumps(answer.to_json()))


# %% on this computer


class ClaudeCodeCommand(StrEnum):
    """
    The parts of the Claude Code command line a local session is started with.
    """

    EXECUTABLE = "claude"
    """
    The command itself.
    """

    PRINT = "--print"
    """
    Runs one prompt to its end without an interactive terminal.
    """


@dataclass(frozen=True)
class LocalSessionStarter(SessionStarter):
    """
    Starts the next session as a Claude Code process in the finished session's checkout,
    which outlives the hook and appends what it prints to
    :attr:`RepositoryStateLocation.AGENTIC_LOOP_LOG`.
    """

    git: GitCommandRunner
    """
    The checkout the session runs in.
    """

    def start(self, session: NextSession) -> None:
        """
        :raises ClaudeCodeMissingError: If no Claude Code command is on the search path.
        """
        executable = shutil.which(ClaudeCodeCommand.EXECUTABLE)
        if executable is None:
            raise ClaudeCodeMissingError(ClaudeCodeCommand.EXECUTABLE)
        log = self.git.repository_state_path(RepositoryStateLocation.AGENTIC_LOOP_LOG)
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as output:
            subprocess.Popen(
                [executable, ClaudeCodeCommand.PRINT, session.prompt],
                cwd=self.git.working_directory,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
