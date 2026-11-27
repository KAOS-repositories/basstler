"""
Stands in for :mod:`basstler.personal_notes.git_identity`, printing the identity path of
a colleague who shares the notes branch without owning its repository.
"""

from __future__ import annotations

from basstler.personal_notes.locations import PersonalNotesProjectLocation

print(
    (PersonalNotesProjectLocation.CONTRIBUTOR_GIT_IDENTITIES / "a-colleague").as_posix()
)
