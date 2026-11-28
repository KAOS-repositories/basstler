"""
The systemd user unit that keeps the locally served plan site running.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from basstler.plan_site.environment import UserDirectoryVariable
from basstler.plan_site.exceptions import UserServiceInstallError
from basstler.plan_site.locations import SiteTemplate, UserServiceLocation
from basstler.render_common import TemplatePage
from basstler.text_file import TextFile

SYSTEMCTL = "systemctl"
"""
The command that controls systemd's units.
"""


class SystemctlWord(StrEnum):
    """
    The words :data:`SYSTEMCTL` is called with.
    """

    USER = "--user"
    DAEMON_RELOAD = "daemon-reload"
    ENABLE = "enable"
    RESTART = "restart"


@dataclass(frozen=True)
class SystemdUserService:
    """
    A user unit running one command from the time the user logs in.
    """

    command: tuple[str, ...]
    """
    The words of the command the unit runs.
    """

    unit_directory: Path
    """
    Where systemd reads the user's units from.
    """

    search_path: str
    """
    The ``PATH`` the command runs with, which has to find ``git`` and ``gh``.
    """

    unit_name: str = UserServiceLocation.PLAN_SITE_UNIT.name
    """
    The unit's file name.
    """

    @classmethod
    def for_current_user(
        cls, command: tuple[str, ...], environment: Mapping[str, str] = os.environ
    ) -> SystemdUserService:
        """
        :param command: The words of the command the unit runs.
        :param environment: The environment naming the user's directories.
        :return: The unit in the user's own configuration directory, running with this
            process's ``PATH``.
        """
        configuration = environment.get(UserDirectoryVariable.CONFIGURATION_HOME)
        base = Path(configuration) if configuration else Path.home() / ".config"
        return cls(
            command,
            base / UserServiceLocation.UNIT_DIRECTORY,
            environment.get(UserDirectoryVariable.SEARCH_PATH, os.defpath),
        )

    @property
    def unit_path(self) -> Path:
        """
        The unit's file.
        """
        return self.unit_directory / self.unit_name

    def render(self) -> str:
        """
        :return: The unit file's text.
        """
        return TemplatePage.render_named_template(
            SiteTemplate.USER_SERVICE.name,
            environment=self.quoted(
                f"{UserDirectoryVariable.SEARCH_PATH}={self.search_path}"
            ),
            command=" ".join(
                self.quoted(word).replace("$", "$$") for word in self.command
            ),
        ).strip()

    @staticmethod
    def quoted(word: str) -> str:
        """
        :param word: One word of a unit's setting.
        :return: The word as systemd reads it back unchanged.
        """
        escaped = word.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%")
        return f'"{escaped}"'

    def install(self) -> None:
        """
        Write the unit, enable it and start it anew.

        :raises UserServiceInstallError: If there is no systemd or it refuses.
        """
        systemctl = shutil.which(SYSTEMCTL)
        if systemctl is None:
            raise UserServiceInstallError(f"{SYSTEMCTL} is not on PATH")
        self.unit_directory.mkdir(parents=True, exist_ok=True)
        TextFile(self.unit_path).write(f"{self.render()}\n")
        for words in (
            (SystemctlWord.DAEMON_RELOAD,),
            (SystemctlWord.ENABLE, self.unit_name),
            (SystemctlWord.RESTART, self.unit_name),
        ):
            completed = subprocess.run(
                [systemctl, SystemctlWord.USER, *words],
                capture_output=True,
                encoding="utf-8",
            )
            if completed.returncode != 0:
                raise UserServiceInstallError(completed.stderr.strip())
