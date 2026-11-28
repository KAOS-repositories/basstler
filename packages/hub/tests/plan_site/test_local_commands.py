"""
Tests for the ``basstler plan-site`` commands' settings.
"""

from __future__ import annotations

import sys
from pathlib import Path

from basstler.github.repository import Repository
from basstler.plan_site import local_commands
from basstler.plan_site.local_commands import ServeSettings, plan_site_app


def test_the_service_runs_serve_with_the_settings_it_was_installed_with():
    settings = ServeSettings(
        port=9000,
        stale_after_minutes=10,
        registry=Repository("owner", "notes"),
        repository=(Repository("owner", "a"), Repository("owner", "b")),
    )

    command = settings.service_command()

    assert command[:3] == (sys.executable, "-m", local_commands.__name__)
    _, bound, _ = plan_site_app.parse_args(list(command[3:]))
    assert bound.kwargs["settings"] == settings


def test_a_directory_that_is_no_checkout_names_no_registry(tmp_path: Path):
    assert ServeSettings().registry_of_checkout(tmp_path) is None
