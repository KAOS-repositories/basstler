"""
The shared fixtures this distribution's tests use.
"""

from __future__ import annotations

from basstler_testing.fixtures import (
    package_environment_of_the_suite,
    python3_directory,
    stub_bin,
)
from basstler_testing.repository_fixtures import (
    fork_checkout,
    scratch_repository,
)

# %% the fixtures pytest finds here

__all__ = [
    "fork_checkout",
    "package_environment_of_the_suite",
    "python3_directory",
    "scratch_repository",
    "stub_bin",
]
