"""
Allow a session to run the plugin's entry point script without a prompt: the hook Claude
Code runs before ``Bash``, which says nothing for any other command.

Usage:
    "${BASSTLER_PYTHON}" -m basstler.plan_site.entry_point_approval < <hook input>
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from cyclopts import App

from basstler.class_property import classproperty
from basstler.exit_codes import StackExitCode
from basstler.session_tool import BuiltInTool
from basstler.json_model import ValidatedJSONModel
from basstler.locations import BasstlerVariable, ClaudeCodeVariable, PluginLocation
from basstler.plan_site.attach_approval import AllowedAttach, AttachAnswer
from basstler.plugin_root import PluginRoot

# %% what Claude Code sends


class ShellArguments(ValidatedJSONModel):
    """
    The command a call of :attr:`BuiltInTool.RUN_SHELL_COMMAND` runs.
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
    The tool's arguments, read as those of :attr:`BuiltInTool.RUN_SHELL_COMMAND`.
    """


# %% the command


@dataclass(frozen=True)
class EntryPointInvocation:
    """
    A command line that runs this plugin's entry point script alone, whether it names
    the plugin root through a variable or by its path, with arguments the shell leaves
    as they are.
    """

    plugin_root: PluginRoot
    """
    The plugin the session runs, the only root an expanded path may name.
    """

    @classmethod
    def of_environment(cls, environment: Mapping[str, str]) -> EntryPointInvocation:
        """
        :param environment: The environment the hook runs in.
        :return: The invocation of the plugin that environment exports.
        :raises basstler.exceptions.PluginRootUnsetError: If no plugin root is exported.
        """
        return cls(PluginRoot.locate(environment))

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
        The plugin root once expanded, a plain absolute path with nothing the shell
        would interpret, below ``/`` or a Windows drive, as a pattern whose group is
        that path.
        """
        return r"(?P<expanded_root>(?:[A-Za-z]:)?/[^\s\"'`$;&|<>()\\]+)"

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

    def matches(self, command: str) -> bool:
        """
        :param command: The command line a session is about to run.
        :return: Whether it is this invocation, with nothing chained to it, and an
            expanded path names this plugin's own root.
        """
        match = self.command_line.fullmatch(command)
        if match is None:
            return False
        expanded_root = match.group("expanded_root")
        if expanded_root is None:
            return True
        return Path(expanded_root).resolve() == self.plugin_root.directory.resolve()

    def permit(self, call: ShellCall) -> AttachAnswer | None:
        """
        :param call: The tool call about to run.
        :return: The answer allowing it when it is this invocation, ``None`` to leave
            the decision to the normal permission flow.
        """
        if call.tool_name != BuiltInTool.RUN_SHELL_COMMAND:
            return None
        if not self.matches(call.tool_input.command):
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
    Print the answer allowing the command on standard output, and nothing when it is not
    the entry point.

    :return: :attr:`StackExitCode.SUCCESS`, also when nothing is printed.
    """
    call = ShellCall.from_json(json.loads(sys.stdin.read()))
    answer = EntryPointInvocation.of_environment(os.environ).permit(call)
    if answer is not None:
        sys.stdout.write(json.dumps(answer.to_json()))
    return StackExitCode.SUCCESS


if __name__ == "__main__":
    app()
