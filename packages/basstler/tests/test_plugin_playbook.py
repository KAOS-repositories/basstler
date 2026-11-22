"""
Tests that this repository's plugin is the one its default playbook builds.
"""

from __future__ import annotations

import pytest
from basstler_testing.constants.paths import RepositoryLocation

from basstler.playbook.playbook import DefaultPlaybook
from basstler.playbook.plugin import PluginFiles
from basstler.plugin_root import PluginRoot


@pytest.fixture(scope="module")
def plugin():
    """
    The repository's plugin, as the default playbook defines it.
    """
    return PluginFiles.from_playbook(
        PluginRoot(RepositoryLocation.PLUGIN), DefaultPlaybook()
    )


def test_the_generated_files_are_built_from_the_playbook(plugin):
    """
    The plugin's ``hooks.json`` and every ``SKILL.md`` are what ``basstler skills
    build`` writes.
    """
    assert plugin.stale_files == ()


def test_every_shipped_skill_is_declared_by_a_contribution(plugin):
    """
    No skill directory of the plugin is left out of every contribution.
    """
    assert plugin.undeclared_skill_names == ()


def test_every_declared_skill_is_shipped(plugin):
    """
    Every skill a contribution declares has its body in the plugin.
    """
    assert plugin.missing_skills == ()
