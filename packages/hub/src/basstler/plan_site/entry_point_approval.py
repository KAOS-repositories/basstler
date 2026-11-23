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
from enum import StrEnum
from pathlib import Path

from cyclopts import App

from basstler.bash import (
    ShellExpansionCharacter,
    ShellListOperator,
    ShellMetacharacter,
    ShellQuote,
)
from basstler.class_property import classproperty
from basstler.exit_codes import StackExitCode
from basstler.session_tool import BuiltInTool
from basstler.json_model import ValidatedJSONModel
from basstler.locations import BasstlerVariable, ClaudeCodeVariable, PluginLocation
from basstler.plan_site.attach_approval import AllowedAttach, AttachAnswer
from basstler.plugin_root import PluginRoot
from basstler.regular_expression import (
    CharacterRange,
    CharacterSet,
    DoubleQuoted,
    RegularExpression,
    Separator,
)

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


class EntryPointGroup(StrEnum):
    """
    The parts of an entry point invocation read back from its match.
    """

    EXPANDED_ROOT = "expanded_root"
    """
    The plugin root, where the command names it by its path.
    """


@dataclass(frozen=True)
class EntryPointInvocation:
    """
    A command line that runs this plugin's entry point script, whether it names the
    plugin root through a variable or by its path, with arguments the shell leaves as
    they are, optionally after a plain directory change and before a plain exit status
    report.
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
    def plain_word(cls) -> RegularExpression:
        """
        A word with nothing the shell would interpret: no metacharacter, expansion or
        quote.

        >>> EntryPointInvocation.plain_word.compiled().match("~/repo; ls")[0]
        '~/repo'
        """
        return CharacterSet.any_except(
            Separator.WHITESPACE,
            *ShellMetacharacter,
            *ShellExpansionCharacter,
            *ShellQuote,
        ).one_or_more()

    @classproperty
    def plugin_root_variable(cls) -> RegularExpression:
        """
        The plugin root as the skills write it, through either variable.

        >>> pattern = EntryPointInvocation.plugin_root_variable.compiled()
        >>> pattern.findall("${CLAUDE_PLUGIN_ROOT} $BASSTLER_PLUGIN_ROOT")
        ['${CLAUDE_PLUGIN_ROOT}', '$BASSTLER_PLUGIN_ROOT']
        """
        variable_name = RegularExpression.either(
            BasstlerVariable.PLUGIN_ROOT, ClaudeCodeVariable.PLUGIN_ROOT
        )
        return RegularExpression.either(
            RegularExpression.sequence("${", variable_name, "}"),
            RegularExpression.sequence("$", variable_name),
        )

    @classproperty
    def plugin_root_path(cls) -> RegularExpression:
        """
        The plugin root once expanded: a plain absolute path, below ``/`` or a Windows
        drive, as a pattern whose group is that path.

        >>> pattern = EntryPointInvocation.plugin_root_path.compiled()
        >>> pattern.findall("C:/plugins/basstler /opt/basstler")
        ['C:/plugins/basstler', '/opt/basstler']
        """
        drive = RegularExpression.sequence(CharacterRange.ASCII_LETTER, ":").optional()
        return RegularExpression.sequence(drive, "/", cls.plain_word).captured_as(
            EntryPointGroup.EXPANDED_ROOT
        )

    @classproperty
    def script(cls) -> RegularExpression:
        """
        The entry point script below the plugin root, optionally double-quoted.

        >>> pattern = EntryPointInvocation.script.compiled()
        >>> bool(pattern.fullmatch('"${CLAUDE_PLUGIN_ROOT}/hooks/basstler.sh"'))
        True
        """
        double_quote = RegularExpression.literal('"').optional()
        return RegularExpression.sequence(
            double_quote,
            RegularExpression.either(cls.plugin_root_variable, cls.plugin_root_path),
            f"/{PluginLocation.ENTRY_POINT_SCRIPT.as_posix()}",
            double_quote,
        )

    @classproperty
    def arguments(cls) -> RegularExpression:
        """
        What may follow the script: words with nothing that chains, substitutes or
        redirects.

        >>> pattern = EntryPointInvocation.arguments.compiled()
        >>> pattern.match(" setup.gate --check | tee log")[0]
        ' setup.gate --check'
        """
        argument = CharacterSet.any_except(
            Separator.WHITESPACE,
            *ShellMetacharacter,
            *ShellExpansionCharacter,
            ShellQuote.ESCAPE,
        ).one_or_more()
        return RegularExpression.sequence(
            Separator.WHITESPACE.one_or_more(), argument
        ).zero_or_more()

    @classproperty
    def directory_change(cls) -> RegularExpression:
        """
        What may come before the script: a change into a directory named by a plain
        word.

        >>> pattern = EntryPointInvocation.directory_change.compiled()
        >>> pattern.match("cd ~/repo && basstler.sh")[0]
        'cd ~/repo && '
        """
        return RegularExpression.sequence(
            "cd",
            Separator.WHITESPACE.one_or_more(),
            cls.plain_word,
            Separator.WHITESPACE.zero_or_more(),
            RegularExpression.either(*ShellListOperator),
            Separator.WHITESPACE.zero_or_more(),
        ).optional()

    @classproperty
    def status_report(cls) -> RegularExpression:
        """
        What may follow the arguments: printing plain text and the script's exit status.

        >>> pattern = EntryPointInvocation.status_report.compiled()
        >>> bool(pattern.fullmatch('; echo "exit status: $?"'))
        True
        """
        plain_text = CharacterSet.any_except(
            ShellQuote.DOUBLE_QUOTE, ShellQuote.ESCAPE, *ShellExpansionCharacter
        ).zero_or_more()
        return RegularExpression.sequence(
            Separator.WHITESPACE.zero_or_more(),
            ShellListOperator.SEQUENTIAL,
            Separator.WHITESPACE.zero_or_more(),
            "echo",
            Separator.WHITESPACE.one_or_more(),
            DoubleQuoted(plain_text, "$?"),
        ).optional()

    @classproperty
    def command_line(cls) -> re.Pattern[str]:
        """
        What a whole command line has to match.

        >>> pattern = EntryPointInvocation.command_line
        >>> script = '"${CLAUDE_PLUGIN_ROOT}/hooks/basstler.sh"'
        >>> bool(pattern.fullmatch(f"cd ~/repo && {script} setup.gate"))
        True
        >>> pattern = EntryPointInvocation.command_line
        >>> bool(pattern.fullmatch(f"{script} setup.gate && rm -r ~"))
        False
        """
        return RegularExpression.sequence(
            Separator.WHITESPACE.zero_or_more(),
            cls.directory_change,
            cls.script,
            cls.arguments,
            cls.status_report,
            Separator.WHITESPACE.zero_or_more(),
        ).compiled()

    def matches(self, command: str) -> bool:
        """
        :param command: The command line a session is about to run.
        :return: Whether it is this invocation, with nothing chained to it but a
            directory change and a status report, and an expanded path names this
            plugin's own root.
        """
        match = self.command_line.fullmatch(command)
        if match is None:
            return False
        expanded_root = match[EntryPointGroup.EXPANDED_ROOT]
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
