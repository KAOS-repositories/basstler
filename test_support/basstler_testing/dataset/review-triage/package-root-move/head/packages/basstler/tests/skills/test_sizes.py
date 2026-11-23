from __future__ import annotations

from .test_documents import skill_documents


def test_sizes():
    assert skill_documents() == []
