"""
Tests for :mod:`basstler.plan.agentic_loop.settings`: the user's loop setting on their
notes branch.
"""

from __future__ import annotations

import tomllib

from basstler.plan.agentic_loop.settings import LoopSettings, LoopSettingsStore

from basstler_testing.scratch_repository import ScratchRepository

# %% the file


def test_the_rendered_file_reads_back_as_the_setting():
    """
    The TOML the store writes parses as the setting it was rendered from.
    """
    settings = LoopSettings(enabled=True, maximum_review_rounds=5)
    assert LoopSettings.from_json(tomllib.loads(settings.render())) == settings


# %% the notes branch


def test_a_notes_branch_without_the_setting_reads_as_the_defaults(
    loop_checkout: ScratchRepository,
):
    """
    A user who never set the loop gets the defaults.
    """
    store = LoopSettingsStore.from_project_root(loop_checkout.project_root)
    assert store.read() == LoopSettings()


def test_a_clone_without_a_notes_branch_reads_as_the_defaults(
    scratch_repository: ScratchRepository,
):
    """
    A clone with no notes branch at all gets the defaults too.
    """
    scratch_repository.write("README.md", "scratch repo\n")
    scratch_repository.commit_everything("initial commit")
    store = LoopSettingsStore.from_project_root(scratch_repository.project_root)
    assert store.read() == LoopSettings()


def test_a_written_setting_is_pushed_and_read_back(loop_checkout: ScratchRepository):
    """
    The notes remote holds the rendered setting, which reads back unchanged.
    """
    store = LoopSettingsStore.from_project_root(loop_checkout.project_root)
    settings = LoopSettings(enabled=True, maximum_review_rounds=4)

    store.write(settings)

    assert (
        loop_checkout.published_file(LoopSettingsStore.settings_path),
        store.read(),
    ) == (settings.render(), settings)
