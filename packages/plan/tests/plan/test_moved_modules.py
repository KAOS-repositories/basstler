"""
Tests for finding where plan's modules that moved into its subpackage went, by
:class:`basstler.document_references.ShippedModules`.
"""

from __future__ import annotations

import pytest

import basstler.plan.manifest_tools
import basstler.plan.size_limits
from basstler.document_references import ShippedModules

# %% modules moved into the plan subpackage


@pytest.mark.parametrize(
    ("cited", "moved_to"),
    [
        ("plan_manifest_tools", basstler.plan.manifest_tools.__name__),
        ("plan_size_limits", basstler.plan.size_limits.__name__),
    ],
)
def test_a_module_moved_into_a_subpackage_is_found_where_it_moved(
    cited: str, moved_to: str
):
    """
    A plan module cited by its old name is found in the subpackage it moved to.
    """
    assert ShippedModules.installed().replacement_for(cited) == moved_to
