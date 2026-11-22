"""
The errors the plan service raises.
"""

from __future__ import annotations

from dataclasses import dataclass

from basstler.environment import HubInstanceVariable
from basstler.exceptions import DataclassException, ExternalCallFailed

# %% configuration


@dataclass
class MissingInstanceSetting(DataclassException, LookupError):
    """
    Raised when an instance starts without one of the settings it needs.
    """

    setting: HubInstanceVariable
    """
    The setting neither its variable nor its file variable gives.
    """

    def error_message(self) -> str:
        return f"The plan service needs {self.setting}, which is not set."

    def suggest_correction(self) -> str:
        return (
            f"Set {self.setting} to its value, or {self.setting.file_variable} to the "
            "path of a file holding it."
        )


# %% deploying


@dataclass
class GoogleCloudCommandFailed(ExternalCallFailed):
    """
    Raised when a ``gcloud`` command a deployment depends on fails.
    """

    arguments: tuple[str, ...]
    """
    The command run, program first.
    """

    @property
    def call(self) -> str:
        return " ".join(self.arguments)


@dataclass
class GoogleCloudNotInstalled(DataclassException, FileNotFoundError):
    """
    Raised when a deployment needs ``gcloud`` and none is on the path.
    """

    def error_message(self) -> str:
        return "Deploying to Cloud Run runs gcloud, which is not on the path."

    def suggest_correction(self) -> str:
        return "Install the Google Cloud CLI and sign in with: gcloud auth login"


@dataclass
class UnsupportedImageRegistry(DataclassException, ValueError):
    """
    Raised when a deployment is given an image outside the registry it can proxy.
    """

    reference: str
    """
    The image reference given.
    """

    registry: str
    """
    The host of the one registry a deployment proxies.
    """

    def error_message(self) -> str:
        return f"The image {self.reference} is not in {self.registry}."

    def suggest_correction(self) -> str:
        return f"Give the image as {self.registry}/<owner>/<repository>/<image>:<tag>."
