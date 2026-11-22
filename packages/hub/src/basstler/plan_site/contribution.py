"""
What basstler-hub adds to the default playbook.
"""

from __future__ import annotations

import basstler.plan_site.attach_approval
import basstler.plan_site.entry_point_approval
from basstler.class_property import classproperty
from basstler.github.repository_attachment import SessionTool
from basstler.locations import PluginLocation
from basstler.playbook.component import PlaybookComponent
from basstler.playbook.contribution import PackageContribution
from basstler.playbook.plugin import PackageModuleCommand, PreToolUseHook


class HubContribution(PackageContribution):
    """
    The hooks that approve, before they run, the calls a plan save makes.
    """

    @classproperty
    def playbook_components(cls) -> tuple[PlaybookComponent, ...]:
        return (
            PreToolUseHook(
                PackageModuleCommand(basstler.plan_site.attach_approval),
                matcher=SessionTool.ATTACH_REPOSITORY,
            ),
            PreToolUseHook(
                PackageModuleCommand(basstler.plan_site.entry_point_approval),
                matcher=SessionTool.RUN_SHELL_COMMAND,
                condition=(
                    f"{SessionTool.RUN_SHELL_COMMAND}"
                    f"(*{PluginLocation.ENTRY_POINT_SCRIPT.name}*)"
                ),
            ),
        )
