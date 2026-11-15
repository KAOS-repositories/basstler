"""
Reading and writing the renames a pull request declares.
"""

from __future__ import annotations

from basstler.review_triage.declaration import TriageDeclaration
from basstler.review_triage.detection import RenameDetection
from basstler.review_triage.renames import Rename, RenameDecisions

from .samples import DescriptionSample

# %% reading a description


def test_a_declaration_comment_is_read():
    """
    The YAML of a description's declaration comment becomes its renames and rejections.
    """
    assert TriageDeclaration.from_description(
        DescriptionSample.DECLARING.read()
    ) == TriageDeclaration({"read_value": "value"}, ("write_value",))


def test_a_description_without_a_declaration_declares_nothing():
    """
    A description with no declaration comment declares no renames.
    """
    assert (
        TriageDeclaration.from_description(DescriptionSample.WITHOUT_DECLARATION.read())
        == TriageDeclaration()
    )


# %% writing and giving a declaration

DECLARED = TriageDeclaration({"read_value": "value"}, ("write_value",))
"""
A declaration of one rename and one rejection.
"""


def test_a_written_comment_reads_back_as_the_same_declaration():
    """
    The comment a declaration writes, inside a description, is read back unchanged.
    """
    description = f"Some text.\n\n{DECLARED.comment()}\n"
    assert TriageDeclaration.from_description(description) == DECLARED


def test_rename_arguments_make_the_same_declaration():
    """
    ``old=new`` arguments and rejected identifiers make the declaration they name.
    """
    rename = TriageDeclaration.rename_separator.join(("read_value", "value"))
    assert TriageDeclaration.from_arguments((rename,), ("write_value",)) == DECLARED


def test_a_declaration_decides_its_renames_for_its_source():
    """
    A declaration accepts its renames, credited to its source, and rejects the rest.
    """
    source = RenameDetection()
    assert DECLARED.decisions(source) == RenameDecisions(
        (Rename("read_value", "value", source),), frozenset({"write_value"})
    )
