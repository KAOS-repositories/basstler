"""
The ``basstler skills`` commands: building the plugin's files from the playbook.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from cyclopts import App

from basstler.exit_codes import ExitCode
from basstler.locations import BasstlerRepositoryLocation, PackageLocation
from basstler.playbook.playbook import PlaybookFile
from basstler.playbook.plugin import PluginFiles
from basstler.standard_streams import StandardStreamHandler

logger = StandardStreamHandler.logger_for(__name__)
"""
This module's logger, which is also what its commands print through.
"""


class SkillsCommand(StrEnum):
    """
    The ``basstler skills`` command group and its commands, by name.
    """

    GROUP = "skills"
    """
    The command group itself.
    """

    BUILD = "build"
    """
    Write the plugin's hook registrations and check its skills against the playbook.
    """

    @property
    def invocation(self) -> str:
        """
        The command line running this command.
        """
        return f"{PackageLocation.DIRECTORY.name} {SkillsCommand.GROUP} {self}"


class SkillsExitCode(ExitCode):
    """
    What a ``basstler skills`` command's exit status tells its caller.
    """

    SUCCESS = 0
    """
    The plugin matches the playbook.
    """

    CHANGES_NEEDED = 1
    """
    A file was rewritten or is out of date, or the plugin's skills and the playbook's
    disagree.
    """


skills_app = App(
    name=SkillsCommand.GROUP,
    help="Build the Claude Code plugin's files from the playbook.",
)
"""
The ``skills`` command group.
"""


@skills_app.command(name=SkillsCommand.BUILD)
def build(*, check: bool = False) -> SkillsExitCode:
    """
    Write the current directory's plugin hook registrations from its playbook, and
    report every skill the plugin and the playbook disagree on.

    :param check: Only report whether the hook registrations are current, writing
        nothing.
    """
    project_root = Path.cwd()
    plugin = PluginFiles.for_playbook(
        project_root / BasstlerRepositoryLocation.PLUGIN,
        PlaybookFile(project_root).read(),
    )
    exit_code = SkillsExitCode.SUCCESS
    for skill_name in plugin.undeclared_skill_names:
        logger.error(
            "The plugin ships the skill %s, which no SkillDefinition in the playbook "
            "declares; declare it in its distribution's contribution or remove it.",
            skill_name,
        )
        exit_code = SkillsExitCode.CHANGES_NEEDED
    for skill in plugin.missing_skills:
        logger.error(
            "The playbook declares the skill %s, but %s carries no instructions.",
            skill.skill_name,
            skill.directory(plugin.plugin_root),
        )
        exit_code = SkillsExitCode.CHANGES_NEEDED
    if plugin.hook_registrations_are_current():
        return exit_code
    if check:
        logger.error(
            "%s is out of date; run `%s`.",
            plugin.hook_registrations_path,
            SkillsCommand.BUILD.invocation,
        )
        return SkillsExitCode.CHANGES_NEEDED
    plugin.write_hook_registrations()
    logger.info("Wrote %s", plugin.hook_registrations_path)
    return SkillsExitCode.CHANGES_NEEDED
