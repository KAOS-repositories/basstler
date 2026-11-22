"""
Tests for :mod:`basstler.playbook.plugin`.
"""

from __future__ import annotations

import shutil

import pytest
from basstler_testing.constants.paths import PlaybookSnippet

import basstler.playbook.skills_command
from basstler.locations import PluginLocation, SkillLocation
from basstler.playbook.plugin import (
    HookDefinition,
    HookEvent,
    PackageModuleCommand,
    PluginFiles,
    PluginScriptCommand,
    SkillDefinition,
)
from basstler.playbook.playbook import Playbook
from basstler.text_file import TextFile

DECLARED_SKILL = SkillDefinition("declared-skill")
"""
The skill the dataset plugin ships and declares.
"""

SESSION_START_HOOK = HookDefinition(
    HookEvent.SESSION_START, PluginScriptCommand(PluginLocation.SESSION_START_SCRIPT)
)
"""
A hook running one of the plugin's scripts on every session start.
"""

SHELL_TOOL_HOOK = HookDefinition(
    HookEvent.PRE_TOOL_USE,
    PackageModuleCommand(basstler.playbook.skills_command),
    matcher="Bash",
    condition="Bash(*basstler.sh*)",
)
"""
A hook running a package module before the shell tool runs the entry point.
"""


@pytest.fixture
def plugin_copy(tmp_path):
    """
    A copy of the dataset plugin that a test may write to.
    """
    return shutil.copytree(PlaybookSnippet.PLUGIN, tmp_path / "plugin")


# %% hook registrations


def test_hook_registrations_group_hooks_by_event_in_event_order():
    """
    Hooks are listed under their event, events in their enumeration's order.
    """
    plugin = PluginFiles(
        PlaybookSnippet.PLUGIN, (), (SHELL_TOOL_HOOK, SESSION_START_HOOK)
    )

    assert (
        plugin.hook_registrations
        == TextFile(PlaybookSnippet.PLUGIN / PluginLocation.HOOK_REGISTRATIONS).read()
    )


def test_hook_registrations_are_current_when_the_file_holds_them():
    """
    A file holding exactly the playbook's hooks is current.
    """
    plugin = PluginFiles(
        PlaybookSnippet.PLUGIN, (), (SESSION_START_HOOK, SHELL_TOOL_HOOK)
    )

    assert plugin.hook_registrations_are_current()


def test_hook_registrations_are_stale_once_a_hook_is_left_out():
    """
    A file still holding a hook the playbook left out is stale.
    """
    plugin = PluginFiles(PlaybookSnippet.PLUGIN, (), (SESSION_START_HOOK,))

    assert not plugin.hook_registrations_are_current()


def test_writing_hook_registrations_makes_them_current(plugin_copy):
    """
    Writing the registrations brings the file up to date.
    """
    plugin = PluginFiles(plugin_copy, (), (SESSION_START_HOOK,))

    plugin.write_hook_registrations()

    assert plugin.hook_registrations_are_current()


# %% skills


def test_a_shipped_skill_no_definition_declares_is_reported():
    """
    A skill directory nothing declares is reported; a directory without instructions is not a skill.
    """
    plugin = PluginFiles(PlaybookSnippet.PLUGIN, (DECLARED_SKILL,), ())

    assert plugin.undeclared_skill_names == ("undeclared-skill",)


def test_a_declared_skill_without_instructions_is_reported():
    """
    The dataset's ``not-a-skill`` directory holds files but no instructions.
    """
    without_instructions = SkillDefinition("not-a-skill")
    plugin = PluginFiles(
        PlaybookSnippet.PLUGIN, (DECLARED_SKILL, without_instructions), ()
    )

    assert plugin.missing_skills == (without_instructions,)


def test_a_skill_directory_is_named_after_the_skill():
    """
    A skill's directory under the plugin's skills carries its name.
    """
    directory = DECLARED_SKILL.directory(PlaybookSnippet.PLUGIN)

    assert (directory / SkillLocation.INSTRUCTIONS).is_file()


def test_the_plugin_files_follow_the_playbooks_skills_and_hooks():
    """
    The plugin takes the playbook's skills and hooks and nothing else.
    """
    playbook = Playbook((DECLARED_SKILL, SESSION_START_HOOK))

    assert PluginFiles.for_playbook(PlaybookSnippet.PLUGIN, playbook) == PluginFiles(
        PlaybookSnippet.PLUGIN, (DECLARED_SKILL,), (SESSION_START_HOOK,)
    )
