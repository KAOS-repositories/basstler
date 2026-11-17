"""
One run of a program: what it printed and how it exited.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from basstler.exceptions import CommandFailed


@dataclass(frozen=True)
class CommandRun:
    """
    What one command printed and how it exited.
    """

    command: tuple[str, ...]
    """
    The program and its arguments.
    """

    output: str
    """
    Its standard output.
    """

    errors: str
    """
    Its standard error.
    """

    exit_status: int
    """
    The status it exited with.
    """

    @classmethod
    def of(
        cls,
        command: list[str],
        directory: Path | None = None,
        environment: dict[str, str] | None = None,
    ) -> CommandRun:
        """
        :param command: The program and its arguments.
        :param directory: Where it runs, the current directory when ``None``.
        :param environment: The environment it runs with, the current one when
            ``None``.
        :return: How it ran, whatever its exit status.
        """
        completed = subprocess.run(
            command,
            cwd=directory,
            env=environment,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        return cls(
            tuple(command), completed.stdout, completed.stderr, completed.returncode
        )

    def finished(self, statuses: frozenset[int] = frozenset({0})) -> CommandRun:
        """
        :param statuses: The exit statuses of a run that did its work.
        :return: This run.
        :raises CommandFailed: If it exited with another status.
        """
        if self.exit_status not in statuses:
            raise CommandFailed(
                status=self.exit_status,
                detail=self.output + self.errors,
                command=self.command,
            )
        return self
