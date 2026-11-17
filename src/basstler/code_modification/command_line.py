"""
The ``basstler code-modification`` commands: reversible changes to Python source.
"""

from __future__ import annotations

from pathlib import Path

from cyclopts import App

from basstler.code_modification.commands import CodeModificationCommand
from basstler.code_modification.relocations import ImportRelocation
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
    old_name: str,
    new_name: str,
    paths: list[Path] | None = None,
    *,
    include_mentions: bool = False,
) -> CodeModificationExitCode:
    """
    Rename a symbol in each Python file in *paths* wherever it is named; a file is
    written only once every file is renamed.

    :param old_name: The identifier to replace.
    :param new_name: The identifier that replaces it.
    :param paths: The Python files to rename in.
    :param include_mentions: Whether comments and strings that mention the old name
        name the new one too.
    """
    symbol_rename = SymbolRename(
        old_name=old_name, new_name=new_name, include_mentions=include_mentions
    )
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


@code_modification_app.command(name=CodeModificationCommand.RELOCATE_IMPORT)
def relocate_import(
    name: str, old_module: str, new_module: str, paths: list[Path] | None = None
) -> CodeModificationExitCode:
    """
    Import a name from the module it moved to in each Python file in *paths*; a file is
    written only once every file is relocated.

    :param name: The name that moved.
    :param old_module: The dotted name of the module it moved out of.
    :param new_module: The dotted name of the module it moved to.
    :param paths: The Python files to relocate the import in.
    """
    relocation = ImportRelocation(
        name=name, old_module=old_module, new_module=new_module
    )
    relocated_sources = {
        source_file: relocation.apply(source_file.parse()).module.code
        for source_file in map(PythonSourceFile, paths or [])
    }
    changed = {
        source_file: source
        for source_file, source in relocated_sources.items()
        if source != source_file.read()
    }
    for source_file, source in changed.items():
        source_file.write(source)
        logger.info("Imported %s from %s in %s", name, new_module, source_file.path)
    if changed:
        return CodeModificationExitCode.CHANGES_MADE
    return CodeModificationExitCode.SUCCESS
