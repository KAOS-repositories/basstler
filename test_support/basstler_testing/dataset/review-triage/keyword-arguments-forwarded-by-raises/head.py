from __future__ import annotations

import pytest


def parse(text: str, base: int) -> int:
    return int(text, base)


def test_parse_rejects_letters():
    pytest.raises(ValueError, parse, text="z", base=10)
