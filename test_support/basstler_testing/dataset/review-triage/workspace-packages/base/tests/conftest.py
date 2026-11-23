from __future__ import annotations

import pytest

from .scratch import Scratch


@pytest.fixture
def scratch():
    return Scratch()
