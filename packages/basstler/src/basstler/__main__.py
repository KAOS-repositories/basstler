"""
The ``basstler`` command: one command tree that each command group of the current
project's playbook is mounted on.
"""

from __future__ import annotations

from functools import partial
from importlib.metadata import version
from pathlib import Path

from cyclopts import App

from basstler.locations import PackageLocation
from basstler.playbook.command_group import CommandGroup
from basstler.playbook.playbook import PlaybookFile

app = App(
    name=PackageLocation.DIRECTORY.name,
    help="Workflow tooling for stacked pull requests and plans.",
    version=partial(version, PackageLocation.DIRECTORY.name),
)
"""
The command tree; a distribution adds a command group through its playbook contribution.
"""

for command_group in PlaybookFile(Path.cwd()).read().components_of(CommandGroup):
    app.command(command_group.app)

if __name__ == "__main__":
    app()
