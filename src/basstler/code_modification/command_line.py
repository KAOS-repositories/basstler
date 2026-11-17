"""
The ``basstler code-modification`` commands: reversible changes to Python source.
"""

from __future__ import annotations

from pathlib import Path

from cyclopts import App

from basstler.code_modification.commands import CodeModificationCommand
from basstler.code_modification.renames import SymbolRename
from basstler.code_modification.source_file import PythonSourceFile
from basstler.exit_codes import ExitCode
from basstler.standard_streams import StandardStreamHandler

logger = StandardStreamHandler.logger_for(__name__)
"""
This module's logger, which is also what its commands print through.
"""


class CodeModificationExitCode(ExitCode):
    """
    What a ``basstler code-modification`` command's exit status tells its caller.
    """

    SUCCESS = 0
    """
    Nothing needed changing.
    """

    CHANGES_MADE = 1
    """
    At least one file was rewritten.
    """


code_modification_app = App(
    name=CodeModificationCommand.GROUP,
    help="Change Python source in ways that can be undone exactly.",
)
"""
The ``code-modification`` command group.
"""


@code_modification_app.command(name=CodeModificationCommand.RENAME)
def rename(
    old_name: str, new_name: str, paths: list[Path] | None = None
) -> CodeModificationExitCode:
    """
    Rename a symbol in each Python file in *paths* wherever it is named; a file is
    written only once every file is renamed.

    :param old_name: The identifier to replace.
    :param new_name: The identifier that replaces it.
    :param paths: The Python files to rename in.
    """
    symbol_rename = SymbolRename(old_name=old_name, new_name=new_name)
    renamed_sources = {
        source_file: symbol_rename.apply(source_file.parse()).module.code
        for source_file in map(PythonSourceFile, paths or [])
    }
    changed = {
        source_file: source
        for source_file, source in renamed_sources.items()
        if source != source_file.read()
    }
    for source_file, source in changed.items():
        source_file.write(source)
        logger.info("Renamed %s to %s in %s", old_name, new_name, source_file.path)
    if changed:
        return CodeModificationExitCode.CHANGES_MADE
    return CodeModificationExitCode.SUCCESS
