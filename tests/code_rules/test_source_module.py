"""
Tests for :mod:`basstler.code_rules.source_module`: what the names in a parsed file
refer to.
"""

from __future__ import annotations

import builtins
import shutil

from basstler.code_rules.source_module import SourceModule

from ..constants.paths import SourceModuleSnippet

# %% names a file never spells


def test_a_name_the_file_never_spells_is_found_without_resolving_its_imports():
    """
    Resolving a file's names is its slowest step, so a file that cannot refer to the
    name is answered from its text alone.
    """
    module = SourceModule(SourceModuleSnippet.REMOVES_NOTHING.value)
    (call,) = module.calls()

    refers = module.refers_to(call.func, f"{shutil.__name__}.{shutil.rmtree.__name__}")

    assert (refers, "qualified_names" in vars(module)) == (False, False)


def test_a_builtin_is_found_in_a_file_that_never_spells_its_module():
    """
    A builtin is named without an import, so its module never appears in the file.
    """
    module = SourceModule(SourceModuleSnippet.BUILTIN_OPEN.value)
    (call,) = module.calls()

    assert module.refers_to(call.func, f"{builtins.__name__}.{open.__name__}")
