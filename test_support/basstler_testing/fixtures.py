"""
Fixtures every distribution's tests use: the package's environment as CI has it, and
directories of stubbed executables.

basstler is imported from the workspace's editable installs, as CI and a session start
install it.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

# A session running the plugin exports BASSTLER_PLUGIN_ROOT as its synced copy, which
# basstler.locations reads on import; pinned before anything imports it, so the suite
# tests this checkout's plugin rather than whichever release that session synced.
os.environ["BASSTLER_PLUGIN_ROOT"] = str(Path(__file__).resolve().parents[2] / "plugin")

from .constants.environment import (
    ConfigurationVariable,
    InterpreterName,
    SearchPathVariable,
)
from .executable_stubs import ExecutableStubDirectory

# %% the package's environment, as CI has it


@pytest.fixture(scope="session")
def python3_directory(tmp_path_factory: pytest.TempPathFactory) -> Path | None:
    """
    :param tmp_path_factory: Makes the directory outside every test's own ``tmp_path``.
    :return: A directory holding a ``python3`` running the suite's interpreter, or
        ``None`` where the interpreter's directory has one, as everywhere but Windows.
    """
    interpreter_directory = Path(sys.executable).parent
    if shutil.which(InterpreterName.PYTHON3, path=str(interpreter_directory)):
        return None
    stubs = ExecutableStubDirectory.create(tmp_path_factory.mktemp("suite-interpreter"))
    stubs.install(InterpreterName.PYTHON3)
    return stubs.path


@pytest.fixture(autouse=True)
def package_environment_of_the_suite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, python3_directory: Path | None
) -> None:
    """
    Give every test an empty package home and the suite's interpreter as ``python3``.

    A hook then runs the package this suite imports, as in CI, and never reads or
    removes the package environments of the machine running the suite.

    :param tmp_path: pytest's per-test temporary directory.
    :param monkeypatch: Sets both variables for this test only.
    :param python3_directory: Where ``python3`` is, when the interpreter's own directory
        has none.
    """
    monkeypatch.setenv(ConfigurationVariable.HOME, str(tmp_path / "basstler-home"))
    search_path = [str(Path(sys.executable).parent)]
    if python3_directory is not None:
        search_path.append(str(python3_directory))
    monkeypatch.setenv(
        SearchPathVariable.EXECUTABLE_SEARCH_PATH,
        os.pathsep.join(
            [*search_path, os.environ[SearchPathVariable.EXECUTABLE_SEARCH_PATH]]
        ),
    )


# %% stubbed executables


@pytest.fixture
def stub_bin(tmp_path: Path) -> ExecutableStubDirectory:
    """
    An empty directory meant to be placed first on a test subprocess's PATH, into which
    a test installs whichever stubbed executable it needs.

    :param tmp_path: pytest's per-test temporary directory.
    :return: The stub directory.
    """
    return ExecutableStubDirectory.create(tmp_path)
