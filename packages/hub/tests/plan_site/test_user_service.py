"""
Tests for installing the local plan site as a systemd user unit.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from basstler.plan_site.exceptions import UserServiceInstallError
from basstler.plan_site.user_service import SystemdUserService

from basstler_testing.executable_stubs import (
    NEEDS_SCRIPT_AS_EXECUTABLE,
    ExecutableStubDirectory,
)


@pytest.fixture
def systemctl_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    :return: Where the stub ``systemctl`` first on ``PATH`` records its calls.
    """
    stubs = ExecutableStubDirectory.create(tmp_path)
    stubs.install("systemctl")
    monkeypatch.setenv("PATH", stubs.ahead_of_inherited_path())
    log = tmp_path / "systemctl.log"
    monkeypatch.setenv("STUB_SYSTEMCTL_LOG", str(log))
    return log


@pytest.fixture
def service(tmp_path: Path) -> SystemdUserService:
    return SystemdUserService(
        command=("/an env/python", "-m", "module", "100%", "$HOME"),
        unit_directory=tmp_path / "units",
        search_path="/usr/bin",
    )


def test_the_unit_runs_the_command_with_every_word_quoted(service: SystemdUserService):
    unit = service.render()

    assert 'ExecStart="/an env/python" "-m" "module" "100%%" "$$HOME"' in unit
    assert 'Environment="PATH=/usr/bin"' in unit


@NEEDS_SCRIPT_AS_EXECUTABLE
def test_installing_writes_the_unit_then_enables_and_restarts_it(
    service: SystemdUserService, systemctl_log: Path
):
    service.install()

    assert service.unit_path.read_text(encoding="utf-8").strip() == service.render()
    assert systemctl_log.read_text(encoding="utf-8").splitlines() == [
        "--user daemon-reload",
        f"--user enable {service.unit_name}",
        f"--user restart {service.unit_name}",
    ]


@NEEDS_SCRIPT_AS_EXECUTABLE
def test_a_refusing_systemctl_stops_the_installation(
    service: SystemdUserService,
    systemctl_log: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("STUB_SYSTEMCTL_EXIT_CODE", "1")

    with pytest.raises(UserServiceInstallError):
        service.install()


def test_a_computer_without_systemd_is_told_so(
    service: SystemdUserService, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    monkeypatch.setenv("PATH", str(tmp_path))

    with pytest.raises(UserServiceInstallError):
        service.install()

    assert not service.unit_path.exists()
