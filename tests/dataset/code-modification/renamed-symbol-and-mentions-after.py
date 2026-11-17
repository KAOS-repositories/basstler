"""
A class, its uses, and the text that merely mentions its name.
"""

from __future__ import annotations

import serialization
from serialization import PythonSerializer, SerializerKind
from serialization import PythonSerializer as Writer


class Handler(PythonSerializer):
    """
    PythonSerializer is not renamed in a docstring.
    """

    def build(self, kind: SerializerKind) -> PythonSerializer:
        # PythonSerializer is not renamed in a comment either.
        label = "PythonSerializer"
        if label:
            return Writer(kind=kind)
        return serialization.PythonSerializer.default()
