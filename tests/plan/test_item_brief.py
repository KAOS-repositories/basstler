"""
Tests for basstler.plan.item_brief: the one brief a session reads before working a plan
item.
"""

from __future__ import annotations

import json
import sys
from typing import Any

import pytest
import yaml

from basstler.github import pull_request_source as pull_request_source_module
from basstler.github.pull_request_state import PullRequestRecord, PullRequestState
from basstler.github.repository_access import PullRequestListState
from basstler.github.repository import PullRequestReference, Repository
from basstler.github.tooling_labels import GitHubLabel
from basstler.locations import PluginLocation, ProjectLocation
from basstler.plan.check_dependency_readiness import ReadinessField
from basstler.plan.item_brief import (
    ItemBrief,
    ItemBriefCommandLine,
    ItemBriefKey,
    ItemBriefOption,
    ItemByBranch,
    ItemByIdentifier,
    main,
)
from basstler.plan.model import (
    ExternalDependency,
    ItemNotTrackedError,
    ItemStatus,
    ManifestKey,
    PlanDocument,
    PlanItem,
    PlanManifest,
)
from basstler.plan.repository_rules import RepositoryRules
from basstler.plan.size_limits import Roadmap

from ..constants.paths import DatasetLocation
from ..fixture_plans import FixturePlanId, ForeignItemId
from ..github.pull_request_api import listing_path
from ..github.recorded_client import RecordedGitHubClient
from ..recorded_pull_requests import RecordedPullRequestSource
from ..scratch_repository import ScratchRepository

# %% the briefed plan

BRIEFED_MANIFEST = PlanManifest.from_file(DatasetLocation.BRIEF_PLAN)
"""
The plan the tests publish and brief an item of.
"""

BRIEFED_ITEM = BRIEFED_MANIFEST.item_named("briefed-item")
"""
The item every brief is read for.
"""

BRIEFED_ITEM_SELECTION = ItemByIdentifier(BRIEFED_ITEM.identifier)
"""
The selection a brief is read with unless a test names another.
"""

FOREIGN_MANIFEST = PlanManifest.from_file(
    DatasetLocation.PLANS / FixturePlanId.OTHER / PlanDocument.MANIFEST
)
"""
The other plan one of the briefed item's dependencies belongs to.
"""


def pull_request_of(
    manifest: PlanManifest, item_identifier: str
) -> PullRequestReference:
    """
    :param manifest: The plan the item belongs to.
    :param item_identifier: The item's id.
    :return: The item's pull request, on the plan's default repository.
    """
    return PullRequestReference(
        Repository.parse(manifest.content[ManifestKey.DEFAULT_REPOSITORY.key]),
        manifest.item_named(item_identifier).content[
            ManifestKey.PULL_REQUEST_NUMBER.key
        ],
    )


@pytest.fixture
def pull_request_source() -> RecordedPullRequestSource:
    """
    :return: The dependencies' pull requests: one merged, one draft, and the foreign
        one out of draft.
    """
    return RecordedPullRequestSource(
        records={
            pull_request_of(BRIEFED_MANIFEST, "merged-dependency"): PullRequestRecord(
                state=PullRequestState.CLOSED, labels=[GitHubLabel.MERGED.value]
            ),
            pull_request_of(BRIEFED_MANIFEST, "draft-dependency"): PullRequestRecord(
                state=PullRequestState.OPEN, draft=True
            ),
            pull_request_of(FOREIGN_MANIFEST, ForeignItemId.READY): PullRequestRecord(
                state=PullRequestState.OPEN
            ),
        }
    )


@pytest.fixture
def briefed_repository(scratch_repository: ScratchRepository) -> ScratchRepository:
    """
    :return: A scratch repository whose notes branch carries the briefed plan and the
        other plan.
    """
    scratch_repository.install_hook_scripts(
        PluginLocation.PERSONAL_NOTES_CONFIGURATION_SCRIPT.name
    )
    scratch_repository.write("README.md", "scratch repo\n")
    scratch_repository.commit_everything("initial commit")
    scratch_repository.publish_notes_branch(
        {
            PlanDocument.MANIFEST.path_within_notes_branch(
                BRIEFED_MANIFEST.identifier
            ): DatasetLocation.BRIEF_PLAN.read_text(encoding="utf-8"),
            PlanDocument.ROADMAP.path_within_notes_branch(
                BRIEFED_MANIFEST.identifier
            ): DatasetLocation.BRIEF_ROADMAP.read_text(encoding="utf-8"),
            ProjectLocation.PLAN_RULES: DatasetLocation.REPOSITORY_RULES.read_text(
                encoding="utf-8"
            ),
            PlanDocument.MANIFEST.path_within_notes_branch(
                FOREIGN_MANIFEST.identifier
            ): (
                DatasetLocation.PLANS / FixturePlanId.OTHER / PlanDocument.MANIFEST
            ).read_text(encoding="utf-8"),
        }
    )
    scratch_repository.resolve_notes_remote_to()
    return scratch_repository


def read_brief(
    repository: ScratchRepository,
    pull_request_source: RecordedPullRequestSource,
    selection: ItemByIdentifier | ItemByBranch = BRIEFED_ITEM_SELECTION,
) -> dict[str, Any]:
    """
    :param repository: The repository whose notes branch carries the plan.
    :param pull_request_source: The live state of the dependencies' pull requests.
    :param selection: Which item to brief.
    :return: The brief, rendered and parsed back.
    """
    brief = ItemBrief.read(
        repository.project_root,
        BRIEFED_MANIFEST.identifier,
        selection,
        pull_request_source,
    )
    return yaml.safe_load(brief.render())


# %% the brief


def test_the_brief_holds_the_plan_header_and_the_item(
    briefed_repository: ScratchRepository,
    pull_request_source: RecordedPullRequestSource,
):
    brief = read_brief(briefed_repository, pull_request_source)
    header = BRIEFED_MANIFEST.item_header(BRIEFED_ITEM)

    assert {key: brief[key] for key in header} == header


def test_the_brief_says_which_dependencies_are_ready_to_build_on(
    briefed_repository: ScratchRepository,
    pull_request_source: RecordedPullRequestSource,
):
    brief = read_brief(briefed_repository, pull_request_source)

    assert [
        (dependency[ReadinessField.IDENTIFIER], dependency[ReadinessField.IS_READY])
        for dependency in brief[ItemBriefKey.DEPENDENCIES]
    ] == list(
        zip(
            BRIEFED_ITEM.content[ManifestKey.DEPENDS_ON.key],
            [True, False, True],
            strict=True,
        )
    )


def test_the_brief_resolves_a_dependency_in_another_plan(
    briefed_repository: ScratchRepository,
    pull_request_source: RecordedPullRequestSource,
):
    brief = read_brief(briefed_repository, pull_request_source)

    assert (
        brief[ItemBriefKey.DEPENDENCIES][-1][ReadinessField.TITLE]
        == FOREIGN_MANIFEST.item_named(ForeignItemId.READY).content[
            ManifestKey.TITLE.key
        ]
    )


def test_the_brief_holds_the_plans_standing_rules(
    briefed_repository: ScratchRepository,
    pull_request_source: RecordedPullRequestSource,
):
    brief = read_brief(briefed_repository, pull_request_source)

    assert (
        brief[ItemBriefKey.STANDING_RULES]
        == Roadmap.from_text(
            DatasetLocation.BRIEF_ROADMAP.read_text(encoding="utf-8")
        ).entries
    )


def test_the_brief_holds_the_repositorys_rules(
    briefed_repository: ScratchRepository,
    pull_request_source: RecordedPullRequestSource,
):
    brief = read_brief(briefed_repository, pull_request_source)

    assert brief[ItemBriefKey.REPOSITORY_RULES] == [
        {"id": rule.identifier, "text": rule.text}
        for rule in RepositoryRules.from_yaml(
            DatasetLocation.REPOSITORY_RULES.read_text(encoding="utf-8")
        ).rules
    ]


def test_a_repository_without_rules_is_briefed_with_none(
    briefed_repository: ScratchRepository,
    pull_request_source: RecordedPullRequestSource,
):
    briefed_repository.remove_from_notes_branch(ProjectLocation.PLAN_RULES)

    brief = read_brief(briefed_repository, pull_request_source)

    assert brief[ItemBriefKey.REPOSITORY_RULES] == []


def test_an_item_is_briefed_the_same_by_its_branch(
    briefed_repository: ScratchRepository,
    pull_request_source: RecordedPullRequestSource,
):
    by_branch = read_brief(
        briefed_repository,
        pull_request_source,
        ItemByBranch(BRIEFED_ITEM.content[ManifestKey.BRANCH.key]),
    )

    assert by_branch == read_brief(briefed_repository, pull_request_source)


def test_an_item_the_plan_does_not_track_is_refused(
    briefed_repository: ScratchRepository,
    pull_request_source: RecordedPullRequestSource,
):
    with pytest.raises(ItemNotTrackedError):
        read_brief(briefed_repository, pull_request_source, ItemByIdentifier("missing"))


# %% command line


def test_the_command_prints_the_brief(
    briefed_repository: ScratchRepository,
    pull_request_source: RecordedPullRequestSource,
    capsys: pytest.CaptureFixture[str],
):
    """
    The command line prints the same brief :meth:`ItemBrief.read` builds.
    """
    ItemBriefCommandLine(pull_request_source, briefed_repository.project_root).app(
        [
            ItemBriefOption.PLAN,
            BRIEFED_MANIFEST.identifier,
            ItemBriefOption.ITEM,
            BRIEFED_ITEM.identifier,
        ],
        result_action="return_value",
    )

    assert yaml.safe_load(capsys.readouterr().out) == read_brief(
        briefed_repository, pull_request_source
    )


def test_the_command_leaves_the_upstream_of_a_forked_plan_repository_unread(
    briefed_repository: ScratchRepository,
    monkeypatch: pytest.MonkeyPatch,
):
    plan_repository = Repository.parse(
        BRIEFED_MANIFEST.content[ManifestKey.DEFAULT_REPOSITORY.key]
    )
    fork = json.loads(DatasetLocation.REPOSITORY_FORK.read_text(encoding="utf-8"))
    upstream = Repository.parse(fork["parent"]["full_name"])
    client = RecordedGitHubClient(
        responses={f"/{plan_repository.api_path}": fork},
        pages={
            listing_path(plan_repository): [[]],
            listing_path(upstream, PullRequestListState.OPEN): [[]],
        },
    )
    monkeypatch.setattr(pull_request_source_module, "GitHubRestClient", lambda: client)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "item_brief",
            ItemBriefOption.PLAN,
            BRIEFED_MANIFEST.identifier,
            ItemBriefOption.ITEM,
            BRIEFED_ITEM.identifier,
        ],
    )
    monkeypatch.chdir(briefed_repository.project_root)

    main()

    assert [
        path for path in client.reads if path.startswith(f"/{upstream.api_path}/")
    ] == []


# %% work stacked on that was not handed over


def test_the_brief_of_an_item_with_external_dependencies_says_what_to_do_with_them():
    """
    The session continuing the item is told to decide what to do with the external
    work, and the records it decides from are the item's own.
    """
    record = ExternalDependency(
        reference="other-plan/some-item",
        title="Some item",
        status=ItemStatus.IN_PROGRESS,
        plan_description="What the other plan is for.",
    )
    item = PlanItem(
        {
            **BRIEFED_ITEM.content,
            ManifestKey.EXTERNAL_DEPENDENCIES.key: [record.content],
        }
    )

    brief = yaml.safe_load(
        ItemBrief(
            manifest=BRIEFED_MANIFEST,
            item=item,
            dependencies=[],
            standing_rules=[],
            repository_rules=RepositoryRules(),
        ).render()
    )

    assert brief[ItemBriefKey.EXTERNAL_DEPENDENCIES_GUIDANCE] == (
        ExternalDependency.guidance
    )


def test_the_brief_of_an_item_without_external_dependencies_has_no_such_guidance(
    briefed_repository: ScratchRepository,
    pull_request_source: RecordedPullRequestSource,
):
    brief = read_brief(briefed_repository, pull_request_source)

    assert ItemBriefKey.EXTERNAL_DEPENDENCIES_GUIDANCE not in brief
