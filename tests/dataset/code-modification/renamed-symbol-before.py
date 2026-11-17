"""
A class, its uses, and the text that merely mentions its name.
"""

from __future__ import annotations

import serialization
from serialization import Serializer, SerializerKind
from serialization import Serializer as Writer


class Handler(Serializer):
    """
    Serializer is not renamed in a docstring.
    """

    def build(self, kind: SerializerKind) -> Serializer:
        # Serializer is not renamed in a comment either.
        label = "Serializer"
        if label:
            return Writer(kind=kind)
        return serialization.Serializer.default()
