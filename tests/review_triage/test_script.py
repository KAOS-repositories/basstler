"""
Tests for ``scripts/review-triage.sh``: how it reads the pull request it is given and
prepares the clone basstler reads that pull request from.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from ..constants.environment import (
    FileMode,
    RecordingPythonStubVariable,
    ReviewTriageScriptVariable,
)
from ..constants.paths import DatasetLocation, RepositoryLocation
from ..script_runner import BashScriptRunner
from basstler.text_file import TextFile

# %% an installed triage

PINNED_COMMIT = "0123456789abcdef0123456789abcdef01234567"
"""
A basstler commit, given in full so the script looks nothing up.
"""

REPOSITORY = "owner/name"
"""
The repository the pull requests under test are opened on.
"""

PULL_REQUEST_NUMBER = "12"
"""
The number of the pull request under test.
"""


@dataclass(frozen=True)
class InstalledTriage:
    """
    The script's home with basstler already installed at :data:`PINNED_COMMIT`, its
    interpreter replaced by one recording what it is asked to run.
    """

    home: Path
    """
    The directory the script keeps its environment and clones in.
    """

    call_log: Path
    """
    The file the interpreter records its arguments in.
    """

    @classmethod
    def create(cls, parent: Path) -> InstalledTriage:
        """
        :param parent: Where to create the home, typically pytest's ``tmp_path``.
        :return: A home whose environment the script takes as installed.
        """
        environment = parent / "home" / "environment"
        interpreter = environment / "bin" / "python"
        interpreter.parent.mkdir(parents=True)
        shutil.copy(DatasetLocation.RECORDING_PYTHON_STUB, interpreter)
        interpreter.chmod(FileMode.EXECUTABLE)
        TextFile(environment / ".basstler-commit").write(f"{PINNED_COMMIT}\n")
        return cls(environment.parent, parent / "python-calls.log")

    def run(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        """
        :param arguments: The script's arguments.
        :return: The finished script.
        """
        return BashScriptRunner(
            project_root=self.home.parent,
            script_path=RepositoryLocation.REVIEW_TRIAGE_SCRIPT,
        ).run(
            *arguments,
            **{
                ReviewTriageScriptVariable.HOME: str(self.home),
                ReviewTriageScriptVariable.REFERENCE: PINNED_COMMIT,
                RecordingPythonStubVariable.CALL_LOG: str(self.call_log),
            },
        )

    def recorded_arguments(self) -> list[str]:
        """
        :return: The arguments the interpreter was given, across every run so far.
        """
        return TextFile(self.call_log).read().splitlines()

    def clone(self, repository: str) -> Path:
        """
        :param repository: A repository as ``owner/name``.
        :return: The script's clone of it.
        """
        return self.home / "repositories" / repository

    def origin_url(self, repository: str) -> str:
        """
        :param repository: A repository as ``owner/name``.
        :return: The URL of the ``origin`` remote of the script's clone of it.
        """
        return subprocess.run(
            ["git", "-C", str(self.clone(repository)), "remote", "get-url", "origin"],
            capture_output=True,
            encoding="utf-8",
            check=True,
        ).stdout.strip()


@pytest.fixture
def installed_triage(tmp_path: Path) -> InstalledTriage:
    """
    :param tmp_path: pytest's per-test directory.
    :return: A home with basstler taken as installed.
    """
    return InstalledTriage.create(tmp_path)


# %% naming the pull request


@pytest.mark.parametrize(
    "pull_request",
    [
        f"https://github.com/{REPOSITORY}/pull/{PULL_REQUEST_NUMBER}",
        f"https://github.com/{REPOSITORY}/pull/{PULL_REQUEST_NUMBER}/files",
        f"{REPOSITORY}#{PULL_REQUEST_NUMBER}",
    ],
)
def test_a_single_argument_naming_the_pull_request_triages_it(
    tmp_path: Path, pull_request: str
) -> None:
    by_repository_and_number = InstalledTriage.create(tmp_path / "separate")
    by_repository_and_number.run(REPOSITORY, PULL_REQUEST_NUMBER, "--mark-viewed")
    by_single_argument = InstalledTriage.create(tmp_path / "single")

    completed = by_single_argument.run(pull_request, "--mark-viewed")

    assert completed.returncode == 0, completed.stderr
    assert (
        by_single_argument.recorded_arguments()
        == by_repository_and_number.recorded_arguments()
    )


def test_a_repository_without_a_number_asks_for_its_open_pull_requests(
    installed_triage: InstalledTriage,
) -> None:
    completed = installed_triage.run(REPOSITORY)

    assert completed.returncode == 0, completed.stderr
    assert installed_triage.recorded_arguments() == ["-", REPOSITORY]


# %% how much is printed

SUMMARY_ONLY_OPTION = "--summary-only"
"""
The option of ``basstler review-triage mark-viewed`` printing only the triage's summary.
"""


def test_marking_viewed_prints_only_the_summary_by_default(
    installed_triage: InstalledTriage,
) -> None:
    completed = installed_triage.run(REPOSITORY, PULL_REQUEST_NUMBER, "--mark-viewed")

    assert completed.returncode == 0, completed.stderr
    assert SUMMARY_ONLY_OPTION in installed_triage.recorded_arguments()


def test_marking_viewed_verbosely_prints_the_whole_triage(
    installed_triage: InstalledTriage,
) -> None:
    completed = installed_triage.run(
        REPOSITORY, PULL_REQUEST_NUMBER, "--mark-viewed", "--verbose"
    )

    assert completed.returncode == 0, completed.stderr
    assert SUMMARY_ONLY_OPTION not in installed_triage.recorded_arguments()


def test_a_report_is_printed_whole_without_verbose(
    installed_triage: InstalledTriage,
) -> None:
    completed = installed_triage.run(REPOSITORY, PULL_REQUEST_NUMBER)

    assert completed.returncode == 0, completed.stderr
    assert SUMMARY_ONLY_OPTION not in installed_triage.recorded_arguments()


# %% the clone's origin


def test_the_clone_names_the_repository_as_its_origin(
    installed_triage: InstalledTriage,
) -> None:
    completed = installed_triage.run(REPOSITORY, PULL_REQUEST_NUMBER)

    assert completed.returncode == 0, completed.stderr
    assert installed_triage.origin_url(REPOSITORY) == (
        f"https://github.com/{REPOSITORY}.git"
    )


def test_a_clone_with_another_origin_is_pointed_at_the_repository(
    installed_triage: InstalledTriage,
) -> None:
    clone = installed_triage.clone(REPOSITORY)
    clone.mkdir(parents=True)
    subprocess.run(["git", "-C", str(clone), "init", "--quiet"], check=True)
    subprocess.run(
        ["git", "-C", str(clone), "remote", "add", "origin", "https://example.com/x"],
        check=True,
    )

    completed = installed_triage.run(REPOSITORY, PULL_REQUEST_NUMBER)

    assert completed.returncode == 0, completed.stderr
    assert installed_triage.origin_url(REPOSITORY) == (
        f"https://github.com/{REPOSITORY}.git"
    )
