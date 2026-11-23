"""
What basstler-core adds to the default playbook.
"""

from __future__ import annotations

from basstler.class_property import classproperty
from basstler.playbook.command_group import CommandGroup
from basstler.playbook.component import PlaybookComponent
from basstler.playbook.contribution import PackageContribution
from basstler.playbook.skills_command import skills_app


class CoreContribution(PackageContribution):
    """
    The ``basstler skills`` commands, which build the plugin from the playbook.
    """

    @classproperty
    def playbook_components(cls) -> tuple[PlaybookComponent, ...]:
        return (CommandGroup(skills_app),)
