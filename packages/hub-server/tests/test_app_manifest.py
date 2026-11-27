"""
The committed App manifest and the manifest an instance registers from it.
"""

from __future__ import annotations

import json

from basstler.github.permission_level import PermissionLevel
from basstler.hub_server.app_manifest import (
    AppCapabilities,
    AppEvent,
    AppManifest,
    AppPermission,
)
from basstler.locations import HubServerTemplate

# %% what the committed manifest declares


class TestCommittedCapabilities:
    """
    What the App may read and which events it receives, as committed.
    """

    def test_every_permission_is_read_only(self):
        capabilities = AppCapabilities.committed()
        assert capabilities.default_permissions == {
            AppPermission.METADATA: PermissionLevel.READ,
            AppPermission.CONTENTS: PermissionLevel.READ,
            AppPermission.PULL_REQUESTS: PermissionLevel.READ,
            AppPermission.CHECKS: PermissionLevel.READ,
            AppPermission.STATUSES: PermissionLevel.READ,
        }

    def test_the_events_are_those_the_plan_pages_change_on(self):
        assert AppCapabilities.committed().default_events == (
            AppEvent.PUSH,
            AppEvent.PULL_REQUEST,
            AppEvent.PULL_REQUEST_REVIEW,
            AppEvent.PULL_REQUEST_REVIEW_THREAD,
            AppEvent.CHECK_SUITE,
            AppEvent.STATUS,
            AppEvent.ISSUE_COMMENT,
            AppEvent.INSTALLATION_REPOSITORIES,
        )

    def test_the_app_is_installable_only_on_its_owners_account(self):
        assert AppCapabilities.committed().public is False

    def test_the_file_holds_no_address_and_no_name(self):
        written = json.loads(HubServerTemplate.APP_MANIFEST.read_text(encoding="utf-8"))
        assert set(written) == {"public", "default_permissions", "default_events"}


# %% the manifest an instance registers


class TestInstanceManifest:
    """
    The committed capabilities with the addresses and the name an instance supplies.
    """

    def manifest(self) -> AppManifest:
        return AppManifest.from_committed(
            name="example-basstlerhub",
            homepage_url="https://hub.example.org",
            webhook_url="https://hub.example.org/webhook",
            redirect_url="http://127.0.0.1:5000/redirect",
        )

    def test_it_keeps_the_committed_capabilities(self):
        manifest = self.manifest()
        committed = AppCapabilities.committed()
        assert (
            manifest.public,
            manifest.default_permissions,
            manifest.default_events,
        ) == (committed.public, committed.default_permissions, committed.default_events)

    def test_it_writes_the_keys_github_reads(self):
        written = self.manifest().to_json()
        assert (
            written["name"],
            written["url"],
            written["hook_attributes"],
            written["redirect_url"],
        ) == (
            "example-basstlerhub",
            "https://hub.example.org",
            {"url": "https://hub.example.org/webhook", "active": True},
            "http://127.0.0.1:5000/redirect",
        )
