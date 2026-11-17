"""
Allow a session to run the fast-forward of the fork's base without a prompt: the hook
Claude Code runs before ``Bash``, which says nothing for any other command.

Usage:
    "${BASSTLER_PYTHON}" -m basstler.plan_site.maintenance_approval < <hook input>
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from enum import StrEnum

from cyclopts import App

from basstler.exit_codes import StackExitCode
from basstler.json_model import ValidatedJSONModel
from basstler.locations import BasstlerVariable, ClaudeCodeVariable, PluginLocation
from basstler.maintenance.commands import FastForwardCommand
from basstler.plan_site.attach_approval import AllowedAttach, AttachAnswer

# %% what Claude Code sends


class ShellTool(StrEnum):
    """
    The Claude Code tool that runs a shell command.
    """

    BASH = "Bash"
    """
    Runs a command in the session's shell.
    """


class ShellArguments(ValidatedJSONModel):
    """
    The command a call of :attr:`ShellTool.BASH` runs.
    """

    command: str
    """
    The command line as the session wrote it.
    """


class ShellCall(ValidatedJSONModel):
    """
    The input Claude Code gives a ``PreToolUse`` hook for a shell command.
    """

    tool_name: str
    """
    The tool about to run.
    """

    tool_input: ShellArguments
    """
    The tool's arguments, read as those of :attr:`ShellTool.BASH`.
    """


# %% the command

ENTRY_POINT_LOCATION = re.escape(PluginLocation.ENTRY_POINT_SCRIPT.as_posix())
"""
The entry point script's path below the plugin root, as a pattern.
"""

PLUGIN_ROOT_REFERENCE = (
    rf"\$(?:\{{(?:{BasstlerVariable.PLUGIN_ROOT}|{ClaudeCodeVariable.PLUGIN_ROOT})\}}"
    rf"|{BasstlerVariable.PLUGIN_ROOT}|{ClaudeCodeVariable.PLUGIN_ROOT})"
)
"""
The plugin root as the skills write it, through either variable, as a pattern.
"""

PLUGIN_ROOT_PATH = r"/[^\s\"'`$;&|<>()\\]+"
"""
The plugin root once expanded, a plain path with nothing the shell would interpret,
as a pattern.
"""


@dataclass(frozen=True)
class FastForwardInvocation:
    """
    The one command line this hook allows: the entry point script, whether written
    through the plugin root variable or by its path, run for the fast-forward alone.
    """

    pattern: re.Pattern[str]
    """
    What the whole command line has to match.
    """

    @classmethod
    def of_plugin(cls) -> FastForwardInvocation:
        """
        :return: The invocation the skills write for the fast-forward.
        """
        module = re.escape(f"maintenance {FastForwardCommand.invoked_as}")
        root = rf"(?:{PLUGIN_ROOT_REFERENCE}|{PLUGIN_ROOT_PATH})"
        script = rf'"?{root}/{ENTRY_POINT_LOCATION}"?'
        return cls(re.compile(rf"\s*{script}\s+{module}\s*"))

    def matches(self, command: str) -> bool:
        """
        :param command: The command line a session is about to run.
        :return: Whether it is this invocation, with nothing chained to it.
        """
        return self.pattern.fullmatch(command) is not None

    def permit(self, call: ShellCall) -> AttachAnswer | None:
        """
        :param call: The tool call about to run.
        :return: The answer allowing it when it is this invocation, ``None`` to leave
            the decision to the normal permission flow.
        """
        if call.tool_name != ShellTool.BASH:
            return None
        if not self.matches(call.tool_input.command):
            return None
        return AttachAnswer(
            AllowedAttach("this is the fast-forward of the fork's base branch")
        )


# %% the command line

app = App(help=__doc__)
"""
The command, which reads the hook input from standard input.
"""


@app.default
def answer_hook() -> StackExitCode:
    """
    Print the answer allowing the command on standard output, and nothing when it is
    not the fast-forward.

    :return: :attr:`StackExitCode.SUCCESS`, also when nothing is printed.
    """
    call = ShellCall.from_json(json.loads(sys.stdin.read()))
    answer = FastForwardInvocation.of_plugin().permit(call)
    if answer is not None:
        sys.stdout.write(json.dumps(answer.to_json()))
    return StackExitCode.SUCCESS


if __name__ == "__main__":
    app()
