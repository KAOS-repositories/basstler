"""
Tests for :mod:`basstler.playbook.plugin`.
"""

from __future__ import annotations

import json
import shutil

import pytest
from basstler_testing.constants.paths import PlaybookSnippet

import basstler.playbook.skills_command
from basstler.locations import PluginLocation
from basstler.playbook.playbook import Playbook
from basstler.playbook.plugin import (
    HookRegistrations,
    HookRegistrationsFile,
    PackageModuleCommand,
    PluginFiles,
    PluginScriptCommand,
    PreToolUseHook,
    SessionStartHook,
)
from basstler.playbook.skill import SkillInstructions
from basstler.plugin_root import PluginRoot
from basstler.text_file import TextFile

from .components import UnshippedSkill, DeclaredSkill

DATASET_PLUGIN = PluginRoot(PlaybookSnippet.PLUGIN)
"""
The dataset plugin, whose hook registrations hold :data:`SESSION_START_HOOK` and
:data:`SHELL_TOOL_HOOK`.
"""

SESSION_START_HOOK = SessionStartHook(
    PluginScriptCommand(PluginLocation.SESSION_START_SCRIPT)
)
"""
A hook running one of the plugin's scripts on every session start.
"""

SHELL_TOOL_HOOK = PreToolUseHook(
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
    return PluginRoot(shutil.copytree(PlaybookSnippet.PLUGIN, tmp_path / "plugin"))


def registrations_file(plugin_root, *hooks):
    """
    :return: The hook registrations file of *plugin_root* holding *hooks*.
    """
    return HookRegistrationsFile(
        plugin_root, PluginFiles(plugin_root, (), hooks).hook_registrations
    )


# %% hook registrations


def test_hook_registrations_group_hooks_by_event_in_event_order():
    """
    Hooks are listed under their event, events in their enumeration's order.
    """
    registrations = registrations_file(
        DATASET_PLUGIN, SHELL_TOOL_HOOK, SESSION_START_HOOK
    )

    assert (
        registrations.text
        == TextFile(DATASET_PLUGIN.path_of(PluginLocation.HOOK_REGISTRATIONS)).read()
    )


def test_hook_registrations_read_back_from_their_file():
    """
    The registrations file parses back into the registrations it was written from.
    """
    registrations = registrations_file(
        DATASET_PLUGIN, SESSION_START_HOOK, SHELL_TOOL_HOOK
    )
    written = TextFile(registrations.path).read()

    assert HookRegistrations.from_json(json.loads(written)) == (
        registrations.registrations
    )


def test_hook_registrations_are_stale_once_a_hook_is_left_out():
    """
    A file still holding a hook the playbook left out is stale.
    """
    assert not registrations_file(DATASET_PLUGIN, SESSION_START_HOOK).is_current()


def test_writing_a_generated_file_makes_it_current(plugin_copy):
    """
    Writing the registrations brings the file up to date.
    """
    registrations = registrations_file(plugin_copy, SESSION_START_HOOK)

    registrations.write()

    assert registrations.is_current()


# %% skills


def test_a_shipped_skill_no_class_declares_is_reported():
    """
    A skill directory nothing declares is reported; a directory without instructions
    is not a skill.
    """
    plugin = PluginFiles(DATASET_PLUGIN, (DeclaredSkill(),), ())

    assert plugin.undeclared_skill_names == ("undeclared",)


def test_a_declared_skill_without_instructions_is_reported():
    """
    A declared skill whose directory holds no instructions is missing.
    """
    plugin = PluginFiles(DATASET_PLUGIN, (DeclaredSkill(), UnshippedSkill()), ())

    assert plugin.missing_skills == (UnshippedSkill(),)


def test_the_generated_files_are_the_registrations_and_each_shipped_skill():
    """
    The plugin generates its hook registrations and the instructions of every skill
    it ships instructions for.
    """
    plugin = PluginFiles(
        DATASET_PLUGIN, (DeclaredSkill(), UnshippedSkill()), (SESSION_START_HOOK,)
    )

    assert plugin.generated_files == (
        HookRegistrationsFile(DATASET_PLUGIN, plugin.hook_registrations),
        SkillInstructions(DATASET_PLUGIN, DeclaredSkill()),
    )


def test_the_dataset_plugin_is_current_with_its_playbook():
    """
    No generated file of the dataset plugin differs from what its playbook builds.
    """
    plugin = PluginFiles(
        DATASET_PLUGIN, (DeclaredSkill(),), (SESSION_START_HOOK, SHELL_TOOL_HOOK)
    )

    assert plugin.stale_files == ()


def test_the_plugin_files_follow_the_playbooks_skills_and_hooks():
    """
    The plugin takes the playbook's skills and hooks and nothing else.
    """
    playbook = Playbook((DeclaredSkill(), SESSION_START_HOOK))

    assert PluginFiles.from_playbook(DATASET_PLUGIN, playbook) == PluginFiles(
        DATASET_PLUGIN, (DeclaredSkill(),), (SESSION_START_HOOK,)
    )
