"""
Checking a notes branch's plans out, when the fetch left their contents on the remote.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from basstler.git.commands import GitCommandRunner
from basstler.locations import ProjectLocation
from basstler.plan.model import PlanDocument
from basstler.plan_site.__main__ import HubSite
from basstler.plan_site.exceptions import PlansCheckoutFailedError
from basstler.plan_site.hub import (
    NotesBranch,
    PlanHub,
    SiteAddress,
)
from basstler.setup.steps import PersonalNotesSetting
from basstler_testing.constants.site import SitePlan, SiteSampleText
from basstler_testing.recorded_pull_requests import RecordedPullRequestSource

from .test_hub import PLAN_MANIFEST, REGISTRY, publish_notes

MANIFEST_PATH = Path(SitePlan.FIRST) / PlanDocument.MANIFEST
"""
The one plan the published notes branch holds.
"""


def fetched_without_contents(tmp_path: Path, files: dict[Path, str]) -> NotesBranch:
    """
    :param tmp_path: A directory of the test's own.
    :param files: The plans directory's files on the published notes branch.
    :return: The branch, fetched the way the site fetches it: the remote serves the
        filtered fetch and objects asked for by id, as GitHub does, so no file content
        is downloaded until it is needed.
    """
    publish_notes(tmp_path / "remotes", REGISTRY, files)
    remote = GitCommandRunner(Path(REGISTRY.clone_url_under(str(tmp_path / "remotes"))))
    remote.run("config", "uploadpack.allowFilter", "true")
    remote.run("config", "uploadpack.allowAnySHA1InWant", "true")
    return NotesBranch.fetch(
        REGISTRY,
        PersonalNotesSetting.BRANCH.default,
        f"file://{(tmp_path / 'remotes').as_posix()}",
        tmp_path / "scratch",
    )


def cut_off(notes: NotesBranch) -> None:
    """
    Point the scratch repository's remote at nothing, so no content can be downloaded.

    :param notes: The fetched branch.
    """
    notes.git.run("remote", "set-url", NotesBranch.remote, "file:///nowhere/at/all.git")


def test_one_prefetch_downloads_every_plan_file(tmp_path: Path):
    notes = fetched_without_contents(
        tmp_path, {MANIFEST_PATH: PLAN_MANIFEST.read_text(encoding="utf-8")}
    )
    contents = notes.git.run(
        "ls-tree", "-r", "--format=%(objectname)", NotesBranch.tip
    ).split()

    notes.prefetch(contents)
    cut_off(notes)

    plans_directory = notes.check_out_plans()
    assert (plans_directory / MANIFEST_PATH).read_text(
        encoding="utf-8"
    ) == PLAN_MANIFEST.read_text(encoding="utf-8")


def test_plans_whose_contents_cannot_be_downloaded_are_refused(tmp_path: Path):
    notes = fetched_without_contents(
        tmp_path, {MANIFEST_PATH: PLAN_MANIFEST.read_text(encoding="utf-8")}
    )
    cut_off(notes)

    with pytest.raises(PlansCheckoutFailedError) as refused:
        notes.check_out_plans()

    assert refused.value.repository == REGISTRY
    assert refused.value.error_output


def test_a_branch_without_plans_checks_out_an_empty_directory(tmp_path: Path):
    notes = fetched_without_contents(tmp_path, {})

    plans_directory = notes.check_out_plans()

    assert plans_directory == notes.git.working_directory / ProjectLocation.PLANS
    assert list(plans_directory.iterdir()) == []


def test_a_repository_whose_plans_cannot_be_checked_out_says_so_on_its_card(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    publish_notes(
        tmp_path / "remotes",
        REGISTRY,
        {MANIFEST_PATH: PLAN_MANIFEST.read_text(encoding="utf-8")},
    )

    def refuse(notes: NotesBranch) -> Path:
        raise PlansCheckoutFailedError(notes.repository, "unable to read sha1 file")

    monkeypatch.setattr(NotesBranch, "check_out_plans", refuse)
    summary = HubSite(
        address=SiteAddress(SiteSampleText.SITE_URL),
        pull_request_source=RecordedPullRequestSource(),
        hub=PlanHub(
            registry=str(REGISTRY),
            repositories=[str(REGISTRY)],
            site_url=SiteSampleText.SITE_URL.value,
        ),
        remote_root=str(tmp_path / "remotes"),
    ).build(tmp_path / "site")

    [card] = summary.repositories
    assert card.error == "cannot check out its plans: unable to read sha1 file"
