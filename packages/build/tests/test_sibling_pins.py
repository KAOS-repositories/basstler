"""
Tests for :mod:`basstler.build.sibling_pins`: pinning every basstler requirement of a
distribution to the version being built.
"""

from __future__ import annotations

from basstler.build.sibling_pins import SiblingPinsHook

# %% pinning


def test_a_basstler_requirement_is_pinned_to_the_built_version(tmp_path):
    """
    A requirement of another basstler distribution names exactly the version being
    built; every other requirement keeps its own bounds.
    """
    hook = SiblingPinsHook(
        str(tmp_path), {"dependencies": ["pyyaml>=6", "basstler-core", "basstler"]}
    )
    metadata = {"version": "1.2.3"}

    hook.update(metadata)

    assert metadata["dependencies"] == [
        "pyyaml>=6",
        "basstler-core==1.2.3",
        "basstler==1.2.3",
    ]


def test_a_distribution_merely_named_alike_is_not_pinned(tmp_path):
    """
    Only ``basstler`` itself and the ``basstler-`` distributions are siblings.
    """
    hook = SiblingPinsHook(str(tmp_path), {"dependencies": ["basstlerish>=2"]})
    metadata = {"version": "1.2.3"}

    hook.update(metadata)

    assert metadata["dependencies"] == ["basstlerish>=2"]
