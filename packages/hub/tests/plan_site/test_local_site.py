"""
Tests for keeping the locally served site's build current.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from basstler.plan_site.local_site import LocalSite, SiteBuild

# %% a build writing a page


@dataclass
class NumberedBuild(SiteBuild):
    """
    Writes a page naming how many builds ran, or fails with :attr:`failure`.
    """

    failure: str | None = None
    """
    Why the next builds fail, ``None`` when they succeed.
    """

    runs: int = 0
    """
    How many builds ran.
    """

    def build(self, output: Path) -> str | None:
        self.runs += 1
        if self.failure is not None:
            return self.failure
        output.mkdir(parents=True)
        (output / "index.html").write_text(f"build {self.runs}", encoding="utf-8")
        return None


@dataclass
class SettableClock:
    """
    A clock a test moves.
    """

    now: datetime = field(default_factory=lambda: datetime(2026, 11, 28, tzinfo=UTC))
    """
    The time it reads.
    """

    def __call__(self) -> datetime:
        return self.now


def page_of(site: LocalSite) -> str:
    return (site.current / "index.html").read_text(encoding="utf-8")


@pytest.fixture
def numbered_build() -> NumberedBuild:
    return NumberedBuild()


@pytest.fixture
def clock() -> SettableClock:
    return SettableClock()


@pytest.fixture
def local_site(
    numbered_build: NumberedBuild, clock: SettableClock, tmp_path: Path
) -> LocalSite:
    return LocalSite(numbered_build, tmp_path, clock=clock)


# %% staleness


def test_the_first_view_builds_the_site(local_site: LocalSite):
    local_site.refresh_if_stale()

    assert page_of(local_site) == "build 1"


def test_a_view_within_the_staleness_default_serves_the_same_build(
    local_site: LocalSite, numbered_build: NumberedBuild, clock: SettableClock
):
    local_site.refresh_if_stale()
    clock.now += local_site.stale_after
    local_site.refresh_if_stale()

    assert numbered_build.runs == 1


def test_a_view_past_the_staleness_default_rebuilds(
    local_site: LocalSite, clock: SettableClock
):
    local_site.refresh_if_stale()
    clock.now += local_site.stale_after + timedelta(seconds=1)
    local_site.refresh_if_stale()

    assert page_of(local_site) == "build 2"


def test_a_refresh_rebuilds_a_fresh_site(local_site: LocalSite):
    local_site.refresh_if_stale()
    local_site.refresh()

    assert page_of(local_site) == "build 2"


# %% a failed build


def test_a_failed_build_keeps_the_last_site_and_says_why(
    local_site: LocalSite, numbered_build: NumberedBuild, clock: SettableClock
):
    local_site.refresh()
    built_at = clock.now
    clock.now += timedelta(hours=1)
    numbered_build.failure = "GitHub is unreachable"

    local_site.refresh()

    assert (page_of(local_site), local_site.failure, local_site.built_at) == (
        "build 1",
        "GitHub is unreachable",
        built_at,
    )


def test_a_view_after_a_failed_build_waits_to_go_stale_before_building_again(
    local_site: LocalSite, numbered_build: NumberedBuild
):
    numbered_build.failure = "no"

    local_site.refresh_if_stale()
    local_site.refresh_if_stale()

    assert numbered_build.runs == 1


def test_a_successful_build_clears_the_failure(
    local_site: LocalSite, numbered_build: NumberedBuild
):
    numbered_build.failure = "no"
    local_site.refresh()
    numbered_build.failure = None

    local_site.refresh()

    assert local_site.failure is None


# %% the directories


def test_only_the_current_and_the_previous_build_are_kept(local_site: LocalSite):
    local_site.refresh()
    first = local_site.current
    local_site.refresh()
    second = local_site.current
    local_site.refresh()

    assert (first.exists(), second.exists(), local_site.current.exists()) == (
        False,
        True,
        True,
    )
