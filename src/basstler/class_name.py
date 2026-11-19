"""
A class's own name, spelled the way a command line or a document spells it.
"""

from __future__ import annotations

import re


class HyphenatedClassName:
    """
    Gives a class the hyphenated, lower-case form of its own name.
    """

    @classmethod
    def hyphenated_class_name(cls, suffix: str = "") -> str:
        """
        :param suffix: A trailing part of the class name to leave out.
        :return: The class name in lower case, words joined by hyphens.
        """
        words = cls.__name__.removesuffix(suffix)
        return re.sub(r"(?<!^)(?=[A-Z])", "-", words).lower()
