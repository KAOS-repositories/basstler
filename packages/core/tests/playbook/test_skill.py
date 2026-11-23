"""
Tests for :mod:`basstler.playbook.skill`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from basstler_testing.constants.paths import PlaybookSnippet

from basstler.locations import PluginSkillLocation, SkillLocation
from basstler.playbook.skill import SkillInstructions
from basstler.plugin_root import PluginRoot
from basstler.text_file import TextFile

from .components import CheckCIStatusSkill, DeclaredSkill

DATASET_PLUGIN = PluginRoot(PlaybookSnippet.PLUGIN)
"""
The dataset plugin, which ships the instructions of :class:`DeclaredSkill`.
"""

# %% naming


def test_a_skill_is_named_and_titled_after_its_class_keeping_acronyms_whole():
    """
    ``CheckCIStatusSkill`` reads as ``check-ci-status``, titled ``Check CI status``.
    """
    assert (CheckCIStatusSkill.skill_name, CheckCIStatusSkill.title) == (
        "check-ci-status",
        "Check CI status",
    )


def test_a_skill_directory_is_named_after_the_skill():
    """
    A skill's directory under the plugin's skills carries its name.
    """
    assert DeclaredSkill().directory(DATASET_PLUGIN) == (
        DATASET_PLUGIN.path_of(PluginSkillLocation.SKILLS) / DeclaredSkill.skill_name
    )


# %% instructions


def test_the_instructions_put_the_frontmatter_and_title_above_the_body():
    """
    The generated ``SKILL.md`` is the dataset's, built from the class and its body.
    """
    instructions = SkillInstructions(DATASET_PLUGIN, DeclaredSkill())

    assert (
        instructions.text
        == TextFile(
            DeclaredSkill().directory(DATASET_PLUGIN) / SkillLocation.INSTRUCTIONS
        ).read()
    )


@pytest.mark.parametrize(
    "plugin_directory", [PlaybookSnippet.STALE_PLUGIN, PlaybookSnippet.BODY_ONLY_PLUGIN]
)
def test_the_instructions_keep_the_body_and_replace_what_is_generated(
    plugin_directory: Path,
):
    """
    Built from instructions whose frontmatter and title are outdated or absent, the text
    is the dataset plugin's: the class's frontmatter and title above the same body.
    """
    instructions = SkillInstructions(PluginRoot(plugin_directory), DeclaredSkill())

    assert instructions.text == SkillInstructions(DATASET_PLUGIN, DeclaredSkill()).text
