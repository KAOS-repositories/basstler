"""
Tests for :mod:`basstler.code_modification.references`: names found by what they refer
to through the imports of their file, not by how they are spelled.
"""

from __future__ import annotations

import shutil

import libcst
from libcst import matchers

from basstler.class_property import classproperty
from basstler.code_modification.patterns import CodePattern
from basstler.code_modification.positions import PositionedModule
from basstler.code_modification.references import ReferenceTo
from basstler.code_modification.source_file import PythonSourceFile

from ..constants.paths import TreeRemovalSnippet

# %% the patterns


class CallOfRemovedTree(CodePattern):
    """
    A call of the function :func:`shutil.rmtree`, whichever way it is imported.
    """

    @classproperty
    def matcher(cls) -> matchers.Call:
        return matchers.Call(
            func=ReferenceTo(f"{shutil.__name__}.{shutil.rmtree.__name__}").matcher
        )


class CallOfShutilMember(CodePattern):
    """
    A call of anything in :mod:`shutil`, whichever way it is imported.
    """

    @classproperty
    def matcher(cls) -> matchers.Call:
        return matchers.Call(func=ReferenceTo(shutil.__name__).matcher)


def sources_found(pattern: type[CodePattern], snippet: TreeRemovalSnippet) -> list[str]:
    """
    :return: The source text of each node of *snippet* that has the shape of *pattern*.
    """
    positioned = PositionedModule(PythonSourceFile(snippet).parse())
    return [
        libcst.Module([]).code_for_node(occurrence.node)
        for occurrence in pattern.found_in(positioned)
    ]


# %% references

IMPORTED_REMOVALS = [
    'filesystem.rmtree(Path("clone"))',
    'rmtree(Path("clone"))',
    'remove_tree(Path("clone"))',
]
"""
The calls of the snippet of imported removals, in the order they appear.
"""


def test_a_function_is_found_under_every_name_the_file_imports_it_by():
    """
    A module imported under another name and a function imported under its own or
    another name all refer to the function.
    """
    assert (
        sources_found(CallOfRemovedTree, TreeRemovalSnippet.IMPORTED_RMTREE)
        == IMPORTED_REMOVALS
    )


def test_a_function_of_the_same_name_that_is_not_imported_from_the_module_is_not_found():
    """
    Spelling the name is not referring to the function.
    """
    assert sources_found(CallOfRemovedTree, TreeRemovalSnippet.OTHER_RMTREE) == []


def test_a_module_is_referred_to_by_the_names_of_what_it_holds():
    """
    A reference to a module also matches a name for something in it.
    """
    assert (
        sources_found(CallOfShutilMember, TreeRemovalSnippet.IMPORTED_RMTREE)
        == IMPORTED_REMOVALS
    )
