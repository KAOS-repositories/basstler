"""
A Google Cloud command line that records every command instead of running it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from basstler.hub_server.cloud_run import (
    CommandResult,
    GoogleCloudCommand,
    GoogleCloudCommandLine,
)

# %% recording commands


@dataclass
class RecordingGoogleCloud(GoogleCloudCommandLine):
    """
    Answers every command with success, except a lookup of something listed as absent.
    """

    project_number: str = "123456789"
    """
    The number every project lookup answers with.
    """

    absent: frozenset[str] = frozenset()
    """
    The names of the secrets and repositories a lookup reports as not existing.
    """

    commands: list[tuple[str, ...]] = field(default_factory=list)
    """
    Every command run, in order.
    """

    def run(self, arguments: tuple[str, ...]) -> CommandResult:
        self.commands.append(arguments)
        if GoogleCloudCommand.DESCRIBE in arguments and self.absent & set(arguments):
            return CommandResult(status=1, output="", error="NOT_FOUND")
        return CommandResult(status=0, output=f"{self.project_number}\n", error="")

    def commands_starting_with(self, *prefix: str) -> list[tuple[str, ...]]:
        """
        :return: The commands recorded whose first arguments are *prefix*.
        """
        return [
            command for command in self.commands if command[: len(prefix)] == prefix
        ]
