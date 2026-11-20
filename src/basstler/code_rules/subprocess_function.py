"""
The pattern of a :mod:`subprocess` function, which the checkers of commands and of their
output share.
"""

from __future__ import annotations

import subprocess

from libcst import matchers

from basstler.class_property import classproperty
from basstler.code_modification.patterns import CodePattern

# %% the pattern


class SubprocessFunction(CodePattern):
    """
    A function of :mod:`subprocess`, named through the module.
    """

    @classproperty
    def matcher(cls) -> matchers.Attribute:
        return matchers.Attribute(value=matchers.Name(subprocess.__name__))
