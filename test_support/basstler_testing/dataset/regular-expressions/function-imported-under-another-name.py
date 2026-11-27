"""
A pattern written as text through a function imported under another name.
"""

from __future__ import annotations

from re import compile as build_pattern

WORDS = build_pattern(r"\w+")
"""
A pattern compiled from text.
"""
