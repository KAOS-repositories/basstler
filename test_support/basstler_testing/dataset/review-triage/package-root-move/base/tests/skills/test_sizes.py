from __future__ import annotations

from tests.skills.test_documents import skill_documents


def test_sizes():
    assert skill_documents() == []
