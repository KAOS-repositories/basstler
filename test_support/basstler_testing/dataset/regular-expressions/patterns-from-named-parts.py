"""
A pattern built from named parts, and the pattern types read off ``re``, which the pattern
check accepts.
"""

from __future__ import annotations

import re

from basstler.regular_expression import CharacterClass

DIGITS: re.Pattern[str] = CharacterClass.DIGIT.one_or_more().compiled()
"""
A pattern built from a named part.
"""
