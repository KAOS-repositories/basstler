"""
What basstler-hub adds to the default playbook.
"""

from __future__ import annotations

import basstler.plan_site.attach_approval
import basstler.plan_site.entry_point_approval
from basstler.class_property import classproperty
from basstler.locations import PluginLocation
from basstler.plan_site.local_commands import plan_site_app
from basstler.playbook.command_group import CommandGroup
from basstler.playbook.component import PlaybookComponent
from basstler.playbook.contribution import PackageContribution
from basstler.playbook.plugin import PackageModuleCommand, PreToolUseHook
from basstler.session_tool import BuiltInTool, CloudSessionTool


class HubContribution(PackageContribution):
    """
    The ``basstler plan-site`` commands, and the hooks that approve, before they run,
    the calls a plan save makes.
    """

    @classproperty
    def playbook_components(cls) -> tuple[PlaybookComponent, ...]:
        return (
            CommandGroup(plan_site_app),
            PreToolUseHook(
                PackageModuleCommand(basstler.plan_site.attach_approval),
                matcher=CloudSessionTool.ATTACH_REPOSITORY,
            ),
            PreToolUseHook(
                PackageModuleCommand(basstler.plan_site.entry_point_approval),
                matcher=BuiltInTool.RUN_SHELL_COMMAND,
                condition=(
                    f"{BuiltInTool.RUN_SHELL_COMMAND}"
                    f"(*{PluginLocation.ENTRY_POINT_SCRIPT.name}*)"
                ),
            ),
        )
