"""
Registering the App from the committed manifest: the flow, the conversion of its code
into credentials, and keeping them.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

from basstler.class_property import classproperty
from basstler.github.client import (
    GitHubRestClient,
    GitHubWriter,
    GitHubWrite,
    HttpMethod,
)
from basstler.github.repository import GitHubAddress
from basstler.hub_server.app_credentials import AppCredentials
from basstler.hub_server.app_manifest import AppManifest
from basstler.hub_server.manifest_flow import ManifestFlow
from basstler.hub_server.secret_store import SecretStore
from typing import Any

# %% the pages and calls of GitHub


@dataclass(frozen=True)
class RegistrationPage:
    """
    The GitHub page an App's manifest is submitted to.
    """

    owner: str | None
    """
    The organization that owns the App; ``None`` for the signed-in user's own account.
    """

    @property
    def url(self) -> str:
        """
        The page's address.
        """
        if self.owner is None:
            return f"{GitHubAddress.WEB}/settings/apps/new"
        return f"{GitHubAddress.WEB}/organizations/{self.owner}/settings/apps/new"


class ManifestConversion(GitHubWrite):
    """
    The call that turns the code of a submitted manifest into the App it registered.
    """

    code: str
    """
    The code GitHub redirected the browser with.
    """

    @classproperty
    def method(cls) -> HttpMethod:
        return HttpMethod.POST

    @property
    def path(self) -> str:
        return f"app-manifests/{self.code}/conversions"

    def to_json(self) -> dict[str, Any]:
        """
        :return: No body: the code is in the path.
        """
        return {}


# %% the registration


@dataclass(frozen=True)
class AppRegistration:
    """
    Registers the App on GitHub and keeps its credentials.
    """

    flow: ManifestFlow
    """
    Submits the manifest and receives the code.
    """

    client: GitHubWriter
    """
    Converts the code into the App's credentials.
    """

    store: SecretStore
    """
    Where the credentials are kept.
    """

    @classmethod
    def for_owner(
        cls,
        owner: str,
        webhook_url: str,
        store: SecretStore,
        homepage_url: str | None = None,
        name: str | None = None,
        personal_account: bool = False,
        client: GitHubWriter | None = None,
    ) -> AppRegistration:
        """
        :param owner: The account or organization that owns the App.
        :param webhook_url: Where GitHub delivers the App's events.
        :param store: Where the credentials are kept.
        :param homepage_url: The App's home page; the address the webhook is on by default.
        :param name: The App's name; one unique to the owner by default.
        :param personal_account: Whether *owner* is the signed-in user rather than an
            organization.
        :param client: Converts the code; a client with the caller's credential by default.
        :return: The registration of an App owned by *owner*.
        """
        webhook = urlsplit(webhook_url)
        return cls(
            flow=ManifestFlow(
                name=name or AppManifest.default_name(owner),
                homepage_url=homepage_url
                or webhook._replace(path="", query="", fragment="").geturl(),
                webhook_url=webhook_url,
                registration_page=RegistrationPage(
                    None if personal_account else owner
                ).url,
            ),
            client=client or GitHubRestClient(),
            store=store,
        )

    def register(self) -> AppCredentials:
        """
        Register the App and keep its credentials.

        :return: The App's credentials.
        :raises RegistrationRefused: If the store already holds an App, or the browser
            is not sent back in time.
        """
        self.store.require_no_app()
        code = self.flow.run()
        credentials = AppCredentials.from_json(
            self.client.send(ManifestConversion(code=code))
        )
        self.store.save(credentials)
        return credentials
