"""
Registering the App: the flow, the conversion of its code and the secret store.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from basstler_testing.github.recorded_client import RecordedGitHubClient

from basstler.github.client import GitHubResponse, GitHubWrite
from basstler.hub_server.app_credentials import AppCredentials
from basstler.hub_server.app_manifest import AppManifest
from basstler.hub_server.app_registration import (
    AppRegistration,
    ManifestConversion,
    RegistrationPage,
)
from basstler.hub_server.exceptions import RegistrationFailure, RegistrationRefused
from basstler.hub_server.manifest_flow import ManifestFlow
from basstler.hub_server.secret_store import SecretFile, SecretStore
from .manifest_browser import RedirectedBrowser

# %% the conversion


class AnswersConversionWithCredentials(RecordedGitHubClient):
    """
    A client answering every write with what GitHub answers a converted manifest.
    """

    answer: dict[str, Any]
    """
    The credentials' payload.
    """

    def attempt_send(self, write: GitHubWrite) -> GitHubResponse:
        self.writes.append(write)
        return GitHubResponse(self.answer)


def registration_in(
    directory: Path, browser: RedirectedBrowser, conversion_response: dict[str, Any]
) -> tuple[AppRegistration, AnswersConversionWithCredentials]:
    """
    :return: A registration saving into *directory*, and the client it converts with.
    """
    client = AnswersConversionWithCredentials()
    client.answer = conversion_response
    return (
        AppRegistration(
            flow=ManifestFlow(
                name="example-basstlerhub",
                homepage_url="https://hub.example.org",
                webhook_url="https://hub.example.org/webhook",
                registration_page=RegistrationPage(owner="example").url,
                open_browser=browser,
            ),
            client=client,
            store=SecretStore(directory),
        ),
        client,
    )


class TestRegistering:
    """
    What registering the App converts, returns and keeps.
    """

    def test_the_code_from_the_redirect_is_converted(
        self, secret_directory: Path, conversion_response: dict[str, Any]
    ):
        registration, client = registration_in(
            secret_directory, RedirectedBrowser(code="the-code"), conversion_response
        )
        registration.register()
        assert client.writes == [ManifestConversion(code="the-code")]

    def test_the_credentials_are_kept_in_the_secret_store(
        self,
        secret_directory: Path,
        conversion_response: dict[str, Any],
        credentials: AppCredentials,
    ):
        registration, _ = registration_in(
            secret_directory, RedirectedBrowser(), conversion_response
        )
        registered = registration.register()
        assert (
            registered,
            (secret_directory / SecretFile.PRIVATE_KEY).read_text(encoding="utf-8"),
        ) == (credentials, credentials.pem)

    def test_a_store_holding_an_app_is_refused_before_the_browser_opens(
        self,
        secret_directory: Path,
        conversion_response: dict[str, Any],
        credentials: AppCredentials,
    ):
        SecretStore(secret_directory).save(credentials)
        browser = RedirectedBrowser()
        registration, client = registration_in(
            secret_directory, browser, conversion_response
        )
        with pytest.raises(RegistrationRefused) as refusal:
            registration.register()
        assert (refusal.value.failure, browser.opened, client.writes) == (
            RegistrationFailure.ALREADY_REGISTERED,
            [],
            [],
        )


# %% what the conversion is


class TestManifestConversion:
    """
    The write that turns a manifest's code into the App.
    """

    def test_it_posts_to_the_conversion_of_the_code(self):
        write = ManifestConversion(code="the-code")
        assert (write.method, write.path) == (
            "POST",
            "app-manifests/the-code/conversions",
        )


# %% where the manifest is registered


class TestRegistrationPage:
    """
    The page the manifest is submitted to.
    """

    def test_an_organization_registers_on_its_own_page(self):
        assert RegistrationPage(owner="example").url == (
            "https://github.com/organizations/example/settings/apps/new"
        )

    def test_a_personal_account_registers_on_the_signed_in_users_page(self):
        assert (
            RegistrationPage(owner=None).url == "https://github.com/settings/apps/new"
        )


# %% building it from the command's arguments


class TestRegistrationForOwner:
    """
    The registration the command's arguments describe.
    """

    def test_the_name_defaults_to_one_unique_to_the_owner(self, secret_directory: Path):
        registration = AppRegistration.for_owner(
            "example",
            webhook_url="https://hub.example.org/webhook",
            store=SecretStore(secret_directory),
        )
        assert registration.flow.name == AppManifest.default_name("example")

    def test_the_homepage_defaults_to_the_instance_the_webhook_is_on(
        self, secret_directory: Path
    ):
        registration = AppRegistration.for_owner(
            "example",
            webhook_url="https://hub.example.org/webhook",
            store=SecretStore(secret_directory),
        )
        assert registration.flow.homepage_url == "https://hub.example.org"

    def test_a_given_name_is_kept(self, secret_directory: Path):
        registration = AppRegistration.for_owner(
            "example",
            webhook_url="https://hub.example.org/webhook",
            name="BasstlerHub",
            store=SecretStore(secret_directory),
        )
        assert registration.flow.name == "BasstlerHub"

    def test_a_personal_account_registers_on_the_signed_in_users_page(
        self, secret_directory: Path
    ):
        registration = AppRegistration.for_owner(
            "example",
            webhook_url="https://hub.example.org/webhook",
            personal_account=True,
            store=SecretStore(secret_directory),
        )
        assert registration.flow.registration_page == RegistrationPage(owner=None).url


# %% the name


class TestDefaultName:
    """
    The name an App gets when none is given.
    """

    def test_it_is_unique_per_owner(self):
        assert AppManifest.default_name("example") == "example-basstlerhub"

    def test_a_name_longer_than_githubs_limit_is_refused(self):
        with pytest.raises(ValueError):
            AppManifest.from_committed(
                name="x" * 35,
                homepage_url="https://hub.example.org",
                webhook_url="https://hub.example.org/webhook",
                redirect_url="http://127.0.0.1:5000/redirect",
            )
