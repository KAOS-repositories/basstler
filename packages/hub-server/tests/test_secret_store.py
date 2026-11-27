"""
The directory an instance's key and secrets are kept in.
"""

from __future__ import annotations

import stat
import sys
from pathlib import Path

import pytest

from basstler.environment import HubServerVariable
from basstler.hub_server.app_credentials import AppCredentials
from basstler.hub_server.exceptions import RegistrationFailure, RegistrationRefused
from basstler.hub_server.secret_store import SecretFile, SecretStore

# %% saving


class TestSavingCredentials:
    """
    Each secret is a file of its own in the store's directory.
    """

    def test_each_secret_is_written_to_its_own_file(
        self, secret_directory: Path, credentials: AppCredentials
    ):
        SecretStore(secret_directory).save(credentials)
        assert {
            file: (secret_directory / file).read_text(encoding="utf-8")
            for file in SecretFile
        } == {
            SecretFile.APP_IDENTIFIER: str(credentials.id),
            SecretFile.CLIENT_IDENTIFIER: credentials.client_id,
            SecretFile.CLIENT_SECRET: credentials.client_secret,
            SecretFile.WEBHOOK_SECRET: credentials.webhook_secret,
            SecretFile.PRIVATE_KEY: credentials.pem,
        }

    @pytest.mark.skipif(sys.platform == "win32", reason="Windows has no file modes")
    def test_only_the_owner_can_read_a_secret(
        self, secret_directory: Path, credentials: AppCredentials
    ):
        SecretStore(secret_directory).save(credentials)
        assert stat.S_IMODE(
            (secret_directory / SecretFile.PRIVATE_KEY).stat().st_mode
        ) == (stat.S_IRUSR | stat.S_IWUSR)

    def test_a_store_holding_an_app_is_never_overwritten(
        self, secret_directory: Path, credentials: AppCredentials
    ):
        store = SecretStore(secret_directory)
        store.save(credentials)
        with pytest.raises(RegistrationRefused) as refusal:
            store.save(credentials)
        assert refusal.value.failure is RegistrationFailure.ALREADY_REGISTERED


# %% where the store is


class TestStoreFromEnvironment:
    """
    The store's directory comes from the environment.
    """

    def test_the_directory_is_the_one_the_variable_names(
        self, monkeypatch: pytest.MonkeyPatch, secret_directory: Path
    ):
        monkeypatch.setenv(HubServerVariable.SECRET_DIRECTORY, str(secret_directory))
        assert SecretStore.from_environment() == SecretStore(secret_directory)

    def test_an_unset_variable_is_refused(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv(HubServerVariable.SECRET_DIRECTORY, raising=False)
        with pytest.raises(RegistrationRefused) as refusal:
            SecretStore.from_environment()
        assert refusal.value.failure is RegistrationFailure.SECRET_DIRECTORY_UNSET
