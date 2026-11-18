"""
Combining the renames of several sources and applying them to identifiers and prose.
"""

from __future__ import annotations

from basstler.review_triage.declaration import DescriptionDeclaration
from basstler.review_triage.detection import MemberRenameDetection, RenameDetection
from basstler.review_triage.python_source import PythonSource
from basstler.review_triage.renames import (
    MemberRename,
    Rename,
    RenameCandidates,
    RenameDecisions,
    RenameMap,
)

from .samples import FileSample

# %% combining sources

DETECTED = Rename("old_name", "new_name", RenameDetection())
"""
A rename an earlier source finds.
"""

DECLARED = Rename("old_name", "newer_name", DescriptionDeclaration())
"""
A later source's rename of the same identifier.
"""

OTHER = Rename("other", "renamed_other", RenameDetection())
"""
A rename of another identifier.
"""


def test_a_later_source_outranks_an_earlier_one():
    """
    A rename of a later source replaces an earlier source's rename of the same
    identifier.
    """
    renames = RenameMap.from_decisions(
        [RenameDecisions((DETECTED, OTHER)), RenameDecisions((DECLARED,))]
    )
    assert renames.renames == (DECLARED, OTHER)


def test_a_rejection_drops_an_earlier_source_rename():
    """
    A rejection removes the rename an earlier source found.
    """
    renames = RenameMap.from_decisions(
        [
            RenameDecisions((DETECTED, OTHER)),
            RenameDecisions(rejected=frozenset({"old_name"})),
        ]
    )
    assert renames.renames == (OTHER,)


MEMBER = MemberRename(
    "package.module.old_name", "package.module.new_name", MemberRenameDetection()
)
"""
A rename of a module member whose old name an earlier source also renames.
"""


def test_rejecting_a_name_drops_the_rename_of_a_member_of_that_name():
    """
    A rejection of an old identifier removes the renames of module members it names.
    """
    renames = RenameMap.from_decisions(
        [
            RenameDecisions((MEMBER, OTHER)),
            RenameDecisions(rejected=frozenset({"old_name"})),
        ]
    )
    assert renames.renames == (OTHER,)


def test_a_member_rename_the_word_rename_makes_everywhere_is_dropped():
    """
    A member rename to the name its old name is renamed to everywhere adds nothing.
    """
    renames = RenameMap.from_decisions([RenameDecisions((DETECTED, MEMBER))])
    assert renames.renames == (DETECTED,)


def test_a_member_rename_to_another_name_than_the_word_rename_is_kept():
    """
    A member rename is kept when the word rename gives its old name another name.
    """
    renames = RenameMap.from_decisions([RenameDecisions((DECLARED, MEMBER))])
    assert renames.renames == (DECLARED, MEMBER)


# %% pairing old and new names by the diff


def substitutions(*pairs: tuple[str, str, int]) -> RenameCandidates:
    """
    :param pairs: Each old identifier, its replacement and how often it was seen.
    :return: The substitutions seen.
    """
    candidates = RenameCandidates()
    for old, new, count in pairs:
        for _ in range(count):
            candidates.add(old, new)
    return candidates


def test_a_stray_substitution_does_not_hide_the_dominant_one():
    """
    An old name replaced once by another new name is still paired with the new name
    that replaces it most often.
    """
    candidates = substitutions(("Pose", "PoseRenamed", 3), ("Pose", "Line", 1))
    assert candidates.dominant_pairs(
        frozenset({"Pose"}), frozenset({"PoseRenamed", "Line"})
    ) == {"Pose": "PoseRenamed"}


def test_a_new_name_more_often_replacing_another_old_name_is_not_paired():
    """
    An old name is not paired with a new name that more often replaces another old name.
    """
    candidates = substitutions(("Resolver", "Renamed", 4), ("Value", "Renamed", 1))
    assert candidates.dominant_pairs(
        frozenset({"Resolver", "Value"}), frozenset({"Renamed"})
    ) == {"Resolver": "Renamed"}


def test_an_old_name_replaced_equally_often_by_two_new_names_is_not_paired():
    """
    A tie between two new names leaves the old name unpaired.
    """
    candidates = substitutions(("Pose", "First", 2), ("Pose", "Second", 2))
    assert (
        candidates.dominant_pairs(frozenset({"Pose"}), frozenset({"First", "Second"}))
        == {}
    )


def test_a_file_that_does_not_parse_contributes_no_substitutions():
    """
    The diff of a file one version of which is not valid Python, such as one holding
    merge conflict markers, is not searched for renamed identifiers.
    """
    change = FileSample.CONFLICT_MARKERS.change()
    candidates = RenameCandidates()
    RenameDetection.collect(
        PythonSource(change.base_text), PythonSource(change.head_text), candidates
    )
    assert candidates.replacements == {}


# %% applying renames


def test_every_renamed_component_of_a_dotted_identifier_is_replaced():
    """
    Each renamed component of a dotted path is replaced.
    """
    renames = RenameMap((DETECTED,))
    assert (
        renames.renamed_identifier("package.old_name.size") == "package.new_name.size"
    )


def test_prose_is_renamed_only_at_whole_words():
    """
    An identifier inside a longer word is left alone.
    """
    renames = RenameMap((DETECTED,))
    assert renames.renamed_prose("old_name, not old_names") == "new_name, not old_names"


def test_renames_swapping_two_identifiers_apply_together():
    """
    Renames apply simultaneously, so two identifiers can swap.
    """
    renames = RenameMap(
        (
            Rename("first", "second", RenameDetection()),
            Rename("second", "first", RenameDetection()),
        )
    )
    assert renames.renamed_prose("first then second") == "second then first"


def test_a_moved_module_path_is_replaced_as_a_prefix():
    """
    A renamed dotted module path is replaced where an identifier starts with it, and
    only there.
    """
    renames = RenameMap((Rename("package.old", "package.new.old", "file move"),))
    assert [
        renames.renamed_identifier(identifier)
        for identifier in ("package.old.Member", "package.older", "other.package.old")
    ] == ["package.new.old.Member", "package.older", "other.package.old"]


def test_an_original_identifier_is_found_from_its_replacement():
    """
    The identifier the base commit used is found from the one replacing it.
    """
    assert RenameMap((DETECTED,)).original_identifier(DETECTED.new) == DETECTED.old


# %% file paths

MOVED_FILE = Rename(
    "repository.py", "storage/repository.py", "file path move", is_file_path=True
)
"""
A moved file's path from the first directory the move changes.
"""


def test_a_file_path_is_renamed_where_it_stands_whole():
    renames = RenameMap((MOVED_FILE,))
    assert renames.renamed_prose("see `repository.py`.") == (
        "see `storage/repository.py`."
    )


def test_a_file_path_is_not_renamed_as_the_end_of_a_longer_path():
    renames = RenameMap((MOVED_FILE,))
    assert renames.renamed_prose("see other/repository.py") == "see other/repository.py"


def test_a_file_path_is_not_a_module_prefix():
    renames = RenameMap((MOVED_FILE,))
    assert renames.renamed_identifier("repository.py") == "repository.py"
