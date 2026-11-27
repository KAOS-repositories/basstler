"""
The directory an instance keeps its App's key and secrets in.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Self

from basstler.environment import HubServerVariable
from basstler.hub_server.app_credentials import AppCredentials
from basstler.hub_server.exceptions import RegistrationFailure, RegistrationRefused
from basstler.text_file import TextFile

OWNER_ONLY_FILE = 0o600
"""
The mode of a secret's file: read and written by its owner alone.
"""

OWNER_ONLY_DIRECTORY = 0o700
"""
The mode of the directory the secrets are kept in.
"""

# %% the files


class SecretFile(StrEnum):
    """
    A file of the secret directory, by its name.
    """

    APP_IDENTIFIER = "app-id"
    """
    The App's numeric identifier.
    """

    CLIENT_IDENTIFIER = "client-id"
    """
    The identifier of the App's OAuth client.
    """

    CLIENT_SECRET = "client-secret"
    """
    The secret of the App's OAuth client.
    """

    WEBHOOK_SECRET = "webhook-secret"
    """
    The secret GitHub signs each webhook delivery with.
    """

    PRIVATE_KEY = "private-key.pem"
    """
    The App's private key.
    """


# %% the store


@dataclass(frozen=True)
class SecretStore:
    """
    A directory holding one file for each of the App's secrets.
    """

    directory: Path
    """
    The directory the files are in.
    """

    @classmethod
    def from_environment(cls) -> Self:
        """
        :return: The store in the directory the environment names.
        :raises RegistrationRefused: If the environment names none.
        """
        directory = HubServerVariable.SECRET_DIRECTORY.read()
        if not directory:
            raise RegistrationRefused(RegistrationFailure.SECRET_DIRECTORY_UNSET)
        return cls(Path(directory))

    def require_no_app(self) -> None:
        """
        :raises RegistrationRefused: If the store already holds an App's secrets.
        """
        if any((self.directory / file).exists() for file in SecretFile):
            raise RegistrationRefused(RegistrationFailure.ALREADY_REGISTERED)

    def save(self, credentials: AppCredentials) -> None:
        """
        Write each secret to its own file, readable by the owner alone.

        :param credentials: The App's credentials.
        :raises RegistrationRefused: If the store already holds an App's secrets.
        """
        self.require_no_app()
        self.directory.mkdir(parents=True, exist_ok=True, mode=OWNER_ONLY_DIRECTORY)
        contents = {
            SecretFile.APP_IDENTIFIER: str(credentials.id),
            SecretFile.CLIENT_IDENTIFIER: credentials.client_id,
            SecretFile.CLIENT_SECRET: credentials.client_secret,
            SecretFile.WEBHOOK_SECRET: credentials.webhook_secret,
            SecretFile.PRIVATE_KEY: credentials.pem,
        }
        for file, text in contents.items():
            path = self.directory / file
            path.touch(mode=OWNER_ONLY_FILE)
            TextFile(path).write(text)
