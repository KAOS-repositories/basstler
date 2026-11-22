"""
Tests for :mod:`basstler.playbook.skills_command`.
"""

from __future__ import annotations

import shutil

import pytest
from basstler_testing.constants.paths import PlaybookSnippet

from basstler.locations import (
    BasstlerRepositoryLocation,
    PluginLocation,
    ProjectLocation,
)
from basstler.playbook.plugin import PluginFiles
from basstler.plugin_root import PluginRoot
from basstler.playbook.playbook import Playbook
from basstler.playbook.skills_command import SkillsExitCode, build
from basstler.text_file import TextFile


@pytest.fixture
def project_with_empty_playbook(tmp_path, monkeypatch):
    """
    A project, as the current directory, holding the dataset plugin and a playbook with
    no components.
    """
    shutil.copytree(
        PlaybookSnippet.PLUGIN, tmp_path / BasstlerRepositoryLocation.PLUGIN
    )
    TextFile(tmp_path / ProjectLocation.PLAYBOOK).write(
        TextFile(PlaybookSnippet.EMPTY / ProjectLocation.PLAYBOOK).read()
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


def registrations_of(project_root):
    """
    :return: The text of the project's plugin hook registrations.
    """
    return TextFile(
        project_root
        / BasstlerRepositoryLocation.PLUGIN
        / PluginLocation.HOOK_REGISTRATIONS
    ).read()


def test_a_check_writes_nothing_and_reports_stale_registrations(
    project_with_empty_playbook,
):
    """
    A check leaves stale registrations as they are and reports them.
    """
    before = registrations_of(project_with_empty_playbook)

    assert (build(check=True), registrations_of(project_with_empty_playbook)) == (
        SkillsExitCode.CHANGES_NEEDED,
        before,
    )


def test_a_build_writes_the_playbooks_registrations(project_with_empty_playbook):
    """
    A build writes the registrations of the project's own playbook.
    """
    plugin_root = PluginRoot(
        project_with_empty_playbook / BasstlerRepositoryLocation.PLUGIN
    )

    build()

    assert (
        registrations_of(project_with_empty_playbook)
        == PluginFiles.from_playbook(plugin_root, Playbook(())).hook_registrations.text
    )


def test_a_build_reports_the_skills_no_playbook_declares(project_with_empty_playbook):
    """
    Once the registrations are current, undeclared skills still fail the build.
    """
    build()

    assert build(check=True) == SkillsExitCode.CHANGES_NEEDED
