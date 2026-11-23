"""
Tests for :mod:`basstler.python_module`: a module as a dotted name that is, or is not,
relative to a root.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from basstler.exceptions import ModuleOutsideRootError
from basstler.python_module import PythonModule

# %% reading and writing the dotted name


def test_a_module_reads_its_dotted_name():
    """
    The parts of ``low.helpers`` are ``low`` and ``helpers``.
    """
    assert PythonModule.from_dotted_name("low.helpers") == PythonModule(
        ("low", "helpers")
    )


def test_a_module_is_written_as_its_dotted_name():
    """
    Writing a module back gives the name it was read from.
    """
    assert str(PythonModule(("low", "helpers"))) == "low.helpers"


def test_the_empty_dotted_name_is_the_module_without_parts():
    """
    A ``from .

    import x`` style statement with no module names the empty module.
    """
    assert PythonModule.from_dotted_name("") == PythonModule(())


# %% top-level package


def test_the_top_level_package_is_the_first_part():
    """
    ``pydantic.fields`` belongs to the package ``pydantic``.
    """
    assert PythonModule.from_dotted_name(
        "pydantic.fields"
    ).top_level_package == PythonModule(("pydantic",))


# %% relative to a root


@pytest.mark.parametrize(
    ("module", "root", "is_within"),
    [
        ("basstler.low.helpers", "basstler", True),
        ("basstler.low", "basstler.low", True),
        ("basstler.low", "basstler.high", False),
        ("basstler_extra.low", "basstler", False),
        ("pydantic", "basstler", False),
    ],
)
def test_a_module_is_within_a_root_when_the_root_is_a_prefix_of_its_parts(
    module, root, is_within
):
    """
    Only whole parts count: ``basstler_extra`` is not within ``basstler``.
    """
    assert (
        PythonModule.from_dotted_name(module).is_within(
            PythonModule.from_dotted_name(root)
        )
        is is_within
    )


def test_a_module_relative_to_a_root_keeps_the_root():
    """
    ``basstler.low.helpers`` relative to ``basstler`` is ``low.helpers`` below
    ``basstler``, so it does not lose where it lies.
    """
    root = PythonModule(("basstler",))
    module = PythonModule.from_dotted_name("basstler.low.helpers")

    assert module.relative_to(root) == PythonModule(("low", "helpers"), root)


def test_a_relative_module_is_written_with_a_leading_dot():
    """
    The leading dot marks the form as relative, as in a relative import.
    """
    module = PythonModule(("low", "helpers"), PythonModule(("basstler",)))

    assert str(module) == ".low.helpers"


def test_a_relative_module_has_an_absolute_form_with_its_root():
    """
    Joining the root's parts back gives ``basstler.low.helpers``.
    """
    module = PythonModule(("low", "helpers"), PythonModule(("basstler",)))

    assert module.absolute == PythonModule(("basstler", "low", "helpers"))


def test_an_absolute_module_is_its_own_absolute_form():
    """
    A module with no root needs no joining.
    """
    module = PythonModule(("basstler", "low"))

    assert module.absolute == module


def test_a_relative_module_is_within_the_root_it_lies_below():
    """
    ``.low`` below ``basstler`` is within ``basstler``, though its own parts are not.
    """
    root = PythonModule(("basstler",))

    assert PythonModule(("low",), root).is_within(root)


def test_the_path_form_of_a_module_is_its_parts_as_directories():
    """
    ``low.helpers`` is the path ``low/helpers`` below its root, without a suffix.
    """
    module = PythonModule(("low", "helpers"), PythonModule(("basstler",)))

    assert module.path == Path("low", "helpers")


def test_a_module_outside_the_root_is_refused():
    """
    A module that does not start with the root has no name relative to it.
    """
    root = PythonModule(("basstler",))
    module = PythonModule(("pydantic", "fields"))

    with pytest.raises(ModuleOutsideRootError) as error:
        module.relative_to(root)

    assert (error.value.module, error.value.root) == (module, root)
