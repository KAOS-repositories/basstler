"""
Allow a session to run the plugin's entry point script without a prompt: the hook Claude
Code runs before ``Bash``, which says nothing for any other command.

Usage:
    "${BASSTLER_PYTHON}" -m basstler.plan_site.entry_point_approval < <hook input>
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass

from cyclopts import App

from basstler.class_property import classproperty
from basstler.exit_codes import StackExitCode
from basstler.github.repository_attachment import SessionTool
from basstler.json_model import ValidatedJSONModel
from basstler.locations import BasstlerVariable, ClaudeCodeVariable, PluginLocation
from basstler.plan_site.attach_approval import AllowedAttach, AttachAnswer

# %% what Claude Code sends


class ShellArguments(ValidatedJSONModel):
    """
    The command a call of :attr:`SessionTool.RUN_SHELL_COMMAND` runs.
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
    The tool's arguments, read as those of :attr:`SessionTool.RUN_SHELL_COMMAND`.
    """


# %% the command


@dataclass(frozen=True)
class EntryPointInvocation:
    """
    A command line that runs the entry point script alone, whether it names the plugin
    root through a variable or by its path, with arguments the shell leaves as they are.
    """

    @classproperty
    def entry_point(cls) -> str:
        """
        The entry point script's path below the plugin root, as a pattern.
        """
        return re.escape(PluginLocation.ENTRY_POINT_SCRIPT.as_posix())

    @classproperty
    def plugin_root_variable(cls) -> str:
        """
        The plugin root as the skills write it, through either variable, as a pattern.
        """
        variables = f"{BasstlerVariable.PLUGIN_ROOT}|{ClaudeCodeVariable.PLUGIN_ROOT}"
        return rf"\$(?:\{{(?:{variables})\}}|{variables})"

    @classproperty
    def plugin_root_path(cls) -> str:
        """
        The plugin root once expanded, a plain path with nothing the shell would
        interpret, as a pattern.
        """
        return r"/[^\s\"'`$;&|<>()\\]+"

    @classproperty
    def arguments(cls) -> str:
        """
        What may follow the script, as a pattern: words with nothing that chains,
        substitutes or redirects.
        """
        return r"(?:\s+[^\s;&|<>`$()\\]+)*"

    @classproperty
    def command_line(cls) -> re.Pattern[str]:
        """
        What a whole command line has to match.
        """
        root = rf"(?:{cls.plugin_root_variable}|{cls.plugin_root_path})"
        script = rf'"?{root}/{cls.entry_point}"?'
        return re.compile(rf"\s*{script}{cls.arguments}\s*")

    @classmethod
    def matches(cls, command: str) -> bool:
        """
        :param command: The command line a session is about to run.
        :return: Whether it is this invocation, with nothing chained to it.
        """
        return cls.command_line.fullmatch(command) is not None

    @classmethod
    def permit(cls, call: ShellCall) -> AttachAnswer | None:
        """
        :param call: The tool call about to run.
        :return: The answer allowing it when it is this invocation, ``None`` to leave
            the decision to the normal permission flow.
        """
        if call.tool_name != SessionTool.RUN_SHELL_COMMAND:
            return None
        if not cls.matches(call.tool_input.command):
            return None
        return AttachAnswer(AllowedAttach("this runs the plugin's own entry point"))


# %% the command line

app = App(help=__doc__)
"""
The command, which reads the hook input from standard input.
"""


@app.default
def answer_hook() -> StackExitCode:
    """
    Print the answer allowing the command on standard output, and nothing when it is
    not the entry point.

    :return: :attr:`StackExitCode.SUCCESS`, also when nothing is printed.
    """
    call = ShellCall.from_json(json.loads(sys.stdin.read()))
    answer = EntryPointInvocation.permit(call)
    if answer is not None:
        sys.stdout.write(json.dumps(answer.to_json()))
    return StackExitCode.SUCCESS


if __name__ == "__main__":
    app()
