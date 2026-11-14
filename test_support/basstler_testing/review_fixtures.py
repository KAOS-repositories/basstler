"""
Fixtures of recorded review answers.
"""

from __future__ import annotations

import pytest

from .upstream_reviews.replay import RecordedResponse, ReplayingClient

# %% recorded answers


@pytest.fixture
def paginated_client() -> ReplayingClient:
    """:return: A client replaying both pages of the recorded review threads."""
    return ReplayingClient(
        [
            RecordedResponse.PULL_REQUEST_PAGE_ONE.load(),
            RecordedResponse.PULL_REQUEST_PAGE_TWO.load(),
        ]
    )
