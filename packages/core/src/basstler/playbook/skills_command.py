"""
The ``basstler skills`` commands: building the plugin's files from the playbook.
"""

from __future__ import annotations

from pathlib import Path

from cyclopts import App

from basstler.exit_codes import ExitCode
from basstler.locations import BasstlerRepositoryLocation
from basstler.playbook.commands import SkillsCommand
from basstler.playbook.playbook import PlaybookFile
from basstler.playbook.plugin import PluginFiles
from basstler.plugin_root import PluginRoot
from basstler.standard_streams import StandardStreamHandler

logger = StandardStreamHandler.logger_for(__name__)
"""
This module's logger, which is also what its commands print through.
"""


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
    name=SkillsCommand.group,
    help="Build the Claude Code plugin's files from the playbook.",
)
"""
The ``skills`` command group.
"""


@skills_app.command(name=SkillsCommand.BUILD)
def build(*, check: bool = False) -> SkillsExitCode:
    """
    Write the current directory's plugin hook registrations and skill instructions
    from its playbook, and report every skill the plugin and the playbook disagree on.

    :param check: Only report which generated files are out of date, writing nothing.
    """
    project_root = Path.cwd()
    plugin = PluginFiles.from_playbook(
        PluginRoot(project_root / BasstlerRepositoryLocation.PLUGIN),
        PlaybookFile(project_root).read(),
    )
    exit_code = SkillsExitCode.SUCCESS
    for skill_name in plugin.undeclared_skill_names:
        logger.error(
            "The plugin ships the skill %s, which no Skill in the playbook declares; "
            "declare it in its distribution's contribution or remove it.",
            skill_name,
        )
        exit_code = SkillsExitCode.CHANGES_NEEDED
    for skill in plugin.missing_skills:
        logger.error(
            "The playbook declares the skill %s, but %s does not exist.",
            skill.skill_name,
            skill.instructions_path(plugin.plugin_root),
        )
        exit_code = SkillsExitCode.CHANGES_NEEDED
    for stale in plugin.stale_files:
        exit_code = SkillsExitCode.CHANGES_NEEDED
        if check:
            logger.error(
                "%s is out of date; run `%s`.",
                stale.path,
                SkillsCommand.BUILD.invocation,
            )
            continue
        stale.write()
        logger.info("Wrote %s", stale.path)
    return exit_code
