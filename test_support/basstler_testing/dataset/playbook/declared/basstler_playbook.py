"""
A project's playbook holding only basstler-core's contribution.
"""

from __future__ import annotations

from basstler.playbook.core_contribution import CoreContribution
from basstler.playbook.playbook import Playbook

BASSTLER_PLAYBOOK = Playbook(CoreContribution.playbook_components)
"""
The playbook the project runs basstler with.
"""
