"""
Tests for :mod:`basstler.python_source_file`.
"""

from __future__ import annotations

import sys

from basstler_testing.constants.paths import PlaybookSnippet

from basstler.locations import ProjectLocation
from basstler.playbook.core_contribution import CoreContribution
from basstler.playbook.playbook import Playbook
from basstler.python_module import PythonModule
from basstler.python_source_file import INITIALIZER_STEM, PythonSourceFile

# %% loading


def test_a_loaded_file_defines_its_modules_variables():
    """
    The module holds what the file assigns at its top level.
    """
    source = PythonSourceFile(PlaybookSnippet.DECLARED / ProjectLocation.PLAYBOOK)

    assert source.load_module().BASSTLER_PLAYBOOK == Playbook(
        CoreContribution.playbook_components
    )


def test_a_loaded_module_is_named_after_its_file_and_left_unregistered():
    """
    Loading names the module after the file's stem and leaves :data:`sys.modules` alone.
    """
    module = PythonSourceFile(
        PlaybookSnippet.EMPTY / ProjectLocation.PLAYBOOK
    ).load_module()

    assert (module.__name__, module.__name__ in sys.modules) == (
        ProjectLocation.PLAYBOOK.stem,
        False,
    )


# %% the module a file holds


def test_a_file_holds_the_module_named_by_its_path_below_the_package(tmp_path):
    """
    ``stack/model.py`` below ``basstler``'s directory holds ``basstler.stack.model``.
    """
    package = PythonModule.from_dotted_name("basstler")
    source = PythonSourceFile(tmp_path / "stack" / "model.py")

    assert source.module_below(tmp_path, package) == PythonModule(
        ("stack", "model"), package
    )


def test_a_package_initializer_holds_the_package_itself(tmp_path):
    """
    ``stack/__init__.py`` holds the package ``basstler.stack``, not a module named
    ``__init__``.
    """
    package = PythonModule.from_dotted_name("basstler")
    source = PythonSourceFile(tmp_path / "stack" / f"{INITIALIZER_STEM}.py")

    assert source.module_below(tmp_path, package) == PythonModule(("stack",), package)
