"""
The indicators YAML is written with.
"""

from __future__ import annotations

from enum import StrEnum


class YamlSyntax(StrEnum):
    """
    The indicators of a YAML document.
    """

    SEQUENCE_ENTRY = "-"
    """
    Starts one entry of a block sequence.
    """

    MAPPING_VALUE = ":"
    """
    Separates a key from its value.
    """

    INDICATOR_SEPARATOR = " "
    """
    Separates an indicator from the content after it.
    """
