"""
The shared fixtures this distribution's tests use.
"""

from __future__ import annotations

from basstler_testing.fixtures import (
    package_environment_of_the_suite,
    python3_directory,
)
from basstler_testing.review_fixtures import (
    paginated_client,
)

# %% the fixtures pytest finds here

__all__ = [
    "package_environment_of_the_suite",
    "paginated_client",
    "python3_directory",
]
