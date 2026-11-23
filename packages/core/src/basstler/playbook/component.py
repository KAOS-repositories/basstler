"""
The base of every part of basstler's behaviour a playbook includes or leaves out.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlaybookComponent:
    """
    One part of basstler's behaviour that a distribution contributes and a playbook
    includes or leaves out; each kind of part is a subclass.
    """
