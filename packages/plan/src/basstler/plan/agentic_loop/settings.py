"""
The user's agentic loop setting, as their personal-notes branch holds it.
"""

from __future__ import annotations

import json
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from basstler.class_property import classproperty
from basstler.git.commands import GitCommandRunner
from basstler.json_model import ValidatedJSONModel
from basstler.locations import ProjectLocation
from basstler.personal_notes.branch import (
    NotesBranchWriter,
    NotesFileChanges,
    NotesWriteOutcome,
    PersonalNotesBranch,
    PersonalNotesLocation,
)
from basstler.shell_configuration import FetchedBranchReference

# %% the setting


class LoopSettings(ValidatedJSONModel):
    """
    Whether finished plan-item stages start the next stage's session, and how often.
    """

    enabled: bool = False
    """
    Whether a finished stage starts the next stage's session.
    """

    maximum_review_rounds: int = 3
    """
    The most reviews one pull request gets in a loop; the resolve of the last one ends
    it.
    """

    def render(self) -> str:
        """
        :return: The settings file's text, in TOML.
        """
        return "".join(
            f"{key} = {json.dumps(value)}\n" for key, value in self.to_json().items()
        )


# %% the setting on the notes branch


@dataclass(frozen=True)
class LoopSettingsStore:
    """
    Reads and writes the user's agentic loop setting on their notes branch.
    """

    branch: PersonalNotesBranch
    """
    The notes branch holding the setting.
    """

    @classproperty
    def settings_path(cls) -> PurePosixPath:
        """
        The settings file's path, relative to the notes branch's root.
        """
        return PurePosixPath(ProjectLocation.PERSONAL_AGENTIC_LOOP_SETTINGS)

    @classmethod
    def from_project_root(cls, project_root: Path) -> LoopSettingsStore:
        """
        :param project_root: The clone whose settings say where the notes are.
        :return: The store over that clone's notes branch.
        """
        return cls(
            PersonalNotesBranch(
                location=PersonalNotesLocation.resolve(project_root, os.environ),
                git=GitCommandRunner(project_root),
            )
        )

    def read(self) -> LoopSettings:
        """
        :return: The setting on the latest notes branch; the defaults when there is no
            notes branch or it holds no setting.
        """
        file = FetchedBranchReference.PERSONAL_NOTES.file_at(self.settings_path)
        if self.branch.fetch_reachable() is None:
            return LoopSettings()
        if not self.branch.git.attempt("cat-file", "-e", file).succeeded:
            return LoopSettings()
        return LoopSettings.from_json(tomllib.loads(self.branch.git.run("show", file)))

    def write(self, settings: LoopSettings) -> NotesWriteOutcome:
        """
        Replace the setting on the notes branch and push it.

        :param settings: The setting the branch is to hold.
        :return: Whether anything was pushed.
        """
        state = "on" if settings.enabled else "off"
        return NotesBranchWriter(self.branch).write(
            NotesFileChanges({self.settings_path: settings.render()}),
            f"Turn the agentic loop {state}",
        )
