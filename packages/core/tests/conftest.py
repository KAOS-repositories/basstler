"""
The shared fixtures this distribution's tests use.
"""

from __future__ import annotations

from basstler_testing.fixtures import (
    package_environment_of_the_suite,
    python3_directory,
)

# %% the fixtures pytest finds here

__all__ = [
    "package_environment_of_the_suite",
    "python3_directory",
]
