"""
Tests for building the locally served site, in this process and in one of its own.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from basstler.plan_site.__main__ import SiteFile
from basstler.plan_site.hub import SiteAddress
from basstler.plan_site.local_build import (
    SubprocessSiteBuild,
    build_local_site,
)
from basstler.plan_site.local_repositories import RepositorySelection

from basstler_testing.constants.site import SitePlan, SiteRepository, SiteSampleText
from basstler_testing.recorded_pull_requests import RecordedPullRequestSource


def test_the_local_build_renders_every_valid_plan_of_the_selected_repositories(
    dataset_remotes: Path, tmp_path: Path
):
    output = tmp_path / "site"

    build_local_site(
        RepositorySelection(
            narrowed_to=(SiteRepository.NOTES.value,),
            remote_root=str(dataset_remotes),
        ),
        SiteAddress(SiteSampleText.SITE_URL.value),
        RecordedPullRequestSource(),
        output,
    )

    plan_page = output / str(SiteRepository.NOTES.value) / SitePlan.FIRST
    assert (plan_page / SiteFile.PAGE).is_file()


def test_a_build_in_a_process_of_its_own_reports_nothing_when_it_succeeds(
    tmp_path: Path,
):
    build = SubprocessSiteBuild((sys.executable, "-c", "pass"))

    assert build.build(tmp_path) is None


def test_a_failed_process_reports_the_end_of_its_error_output(tmp_path: Path):
    build = SubprocessSiteBuild((sys.executable, "-m", "basstler.no_such_module"))

    assert "basstler.no_such_module" in build.build(tmp_path)
