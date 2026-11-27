"""
Functions named as the ones of ``re`` that are not those, and the builtin ``compile``.
"""

from __future__ import annotations


def search(needle, haystack):
    """
    :return: Whether *haystack* holds *needle*.
    """
    return needle in haystack


def run(source):
    """
    :return: The code object of *source*, which is not a pattern.
    """
    return compile(source, "<source>", "exec")


FOUND = search("a", "abc")
"""
A call of the function above.
"""
