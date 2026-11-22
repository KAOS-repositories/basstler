"""
Tests for :mod:`basstler.module`: a module as a dotted name that is, or is not, relative
to a root.
"""

from __future__ import annotations

import pytest

from basstler.exceptions import ModuleOutsideRootError
from basstler.module import Module

# %% reading and writing the dotted name


def test_a_module_reads_its_dotted_name():
    """
    The parts of ``low.helpers`` are ``low`` and ``helpers``.
    """
    assert Module.from_dotted_name("low.helpers") == Module(("low", "helpers"))


def test_a_module_is_written_as_its_dotted_name():
    """
    Writing a module back gives the name it was read from.
    """
    assert str(Module(("low", "helpers"))) == "low.helpers"


def test_the_empty_dotted_name_is_the_module_without_parts():
    """
    A ``from .

    import x`` style statement with no module names the empty module.
    """
    assert Module.from_dotted_name("") == Module(())


# %% top-level package


def test_the_top_level_package_is_the_first_part():
    """
    ``pydantic.fields`` belongs to the package ``pydantic``.
    """
    assert Module.from_dotted_name("pydantic.fields").top_level_package == Module(
        ("pydantic",)
    )


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
        Module.from_dotted_name(module).is_within(Module.from_dotted_name(root))
        is is_within
    )


def test_a_module_relative_to_a_root_drops_the_root():
    """
    ``basstler.low.helpers`` relative to ``basstler`` is ``low.helpers``.
    """
    module = Module.from_dotted_name("basstler.low.helpers")

    assert module.relative_to(Module(("basstler",))) == Module(("low", "helpers"))


def test_a_module_outside_the_root_is_refused():
    """
    A module that does not start with the root has no name relative to it.
    """
    root = Module(("basstler",))
    module = Module(("pydantic", "fields"))

    with pytest.raises(ModuleOutsideRootError) as error:
        module.relative_to(root)

    assert (error.value.module, error.value.root) == (module, root)
