"""
The shared fixtures this distribution's tests use.
"""

from __future__ import annotations

from basstler_testing.browser_fixtures import (
    browser,
    browser_page,
)
from basstler_testing.fixtures import (
    package_environment_of_the_suite,
    python3_directory,
)
from basstler_testing.repository_fixtures import (
    fork_checkout,
)

# %% the fixtures pytest finds here

__all__ = [
    "browser",
    "browser_page",
    "fork_checkout",
    "package_environment_of_the_suite",
    "python3_directory",
]
