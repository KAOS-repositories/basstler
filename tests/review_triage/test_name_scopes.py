"""
Tests for the names each scope of a file binds.
"""

from __future__ import annotations

from basstler.review_triage.name_scopes import NameScope, UnknownValue
from basstler.review_triage.python_source import PythonSource

from .samples import ScopeSample

# %% names declared global


def test_a_name_a_nested_function_declares_global_is_bound_to_an_unknown_value():
    """
    A ``global`` statement inside a nested function's block binds its name in the scope
    holding that function, to a value not followed.
    """
    module = PythonSource.from_text(ScopeSample.GLOBAL_IN_NESTED_FUNCTION.read())

    scope = NameScope.opened_by(module.tree.body[1])

    assert scope.bindings["enabled"] == (UnknownValue(),)


# %% one source of each text


def test_a_text_in_a_package_is_one_source():
    """
    Asking twice for the source of a text in a package gives the same source, which is
    another one in another package.
    """
    text = ScopeSample.GLOBAL_IN_NESTED_FUNCTION.read()

    assert PythonSource.from_text(text, ("package",)) is PythonSource.from_text(
        text, ("package",)
    )
    assert PythonSource.from_text(text, ("package",)) is not PythonSource.from_text(
        text
    )
