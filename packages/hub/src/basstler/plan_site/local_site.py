"""
The build of the locally served plan site, rebuilt when it is viewed and stale.
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from basstler.directory_tree import DirectoryTree

# %% building


class SiteBuild(ABC):
    """
    Writes the whole site into a directory.
    """

    @abstractmethod
    def build(self, output: Path) -> str | None:
        """
        :param output: The directory to write the site into, which does not exist.
        :return: ``None`` on success, otherwise why the build failed.
        """


# %% the current build


@dataclass
class LocalSite:
    """
    The latest successful build, and why a later one failed.
    """

    site_build: SiteBuild
    """
    What builds the site.
    """

    directory: Path
    """
    Where each build gets a directory of its own.
    """

    stale_after: timedelta = timedelta(minutes=5)
    """
    How old the last attempt to build may be before a view builds again.
    """

    clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    """
    Tells the current time.
    """

    current: Path | None = field(default=None, init=False)
    """
    The directory of the build to serve, ``None`` before one succeeded.
    """

    built_at: datetime | None = field(default=None, init=False)
    """
    When :attr:`current` was built.
    """

    failure: str | None = field(default=None, init=False)
    """
    Why the last build failed, ``None`` when it succeeded.
    """

    attempted_at: datetime | None = field(default=None, init=False)
    """
    When the last build was started.
    """

    attempts: int = field(default=0, init=False)
    """
    How many builds were started.
    """

    lock: threading.RLock = field(default_factory=threading.RLock, init=False)
    """
    Held while building, so views arriving together build once.
    """

    def refresh_if_stale(self) -> None:
        """
        :meth:`refresh` when never built or the last attempt is past
        :attr:`stale_after`.
        """
        with self.lock:
            if (
                self.attempted_at is None
                or self.clock() - self.attempted_at > self.stale_after
            ):
                self.refresh()

    def refresh(self) -> None:
        """
        Build the site anew, keeping the current build when that fails.
        """
        with self.lock:
            self.attempted_at = self.clock()
            self.attempts += 1
            output = self.directory / f"build-{self.attempts}"
            self.failure = self.site_build.build(output)
            if self.failure is not None:
                DirectoryTree(output).remove()
                return
            previous, self.current = self.current, output
            self.built_at = self.attempted_at
            # The previous build stays for requests still reading it.
            for older in self.directory.iterdir():
                if older not in (previous, self.current):
                    DirectoryTree(older).remove()
