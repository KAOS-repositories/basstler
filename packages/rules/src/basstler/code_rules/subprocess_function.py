"""
The pattern of a :mod:`subprocess` function, which the checkers of commands and of their
output share.
"""

from __future__ import annotations

import subprocess

from libcst import matchers

from basstler.class_property import classproperty
from basstler.code_modification.patterns import CodePattern
from basstler.code_modification.references import ReferenceTo

# %% the pattern


class SubprocessFunction(CodePattern):
    """
    A function of :mod:`subprocess`, whichever way the file imports it.
    """

    @classproperty
    def matcher(cls) -> matchers.MatchMetadataIfTrue:
        return ReferenceTo(subprocess.__name__).matcher
