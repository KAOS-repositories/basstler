"""
Tests that the plugin's documents, and notes naming only what this release ships, cite
no name the installed package lacks.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from basstler.document_references import CitedNames, ShippedModules

from basstler_testing.constants.paths import DatasetLocation, RepositoryLocation
from basstler.text_file import TextFile

# %% names the whole release ships


def test_notes_naming_only_shipped_names_report_nothing():
    """
    Notes citing only names this release ships report no stale name.
    """
    notes = TextFile(DatasetLocation.NOTES_CITING_SHIPPED_NAMES).read()

    assert CitedNames.in_text(notes).stale(ShippedModules.installed()) == []


def plugin_documents() -> list[Path]:
    """
    :return: Every document and script the plugin ships, which sessions read or run.
    """
    return sorted(
        path
        for pattern in ("*.md", "*.sh")
        for path in RepositoryLocation.PLUGIN.value.rglob(pattern)
    )


@pytest.mark.parametrize(
    "document",
    plugin_documents(),
    ids=lambda path: str(path.relative_to(RepositoryLocation.PLUGIN.value)),
)
def test_no_plugin_document_cites_a_name_this_release_does_not_ship(document: Path):
    """
    Every document the plugin ships cites only names this release ships.
    """
    cited = CitedNames.in_text(TextFile(document).read())

    assert cited.stale(ShippedModules.installed()) == []
