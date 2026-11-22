"""
The failures of registering the App.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from basstler.environment import HubServerVariable
from basstler.exceptions import DataclassException

# %% what refuses a registration


class RegistrationFailure(StrEnum):
    """
    Why a registration cannot proceed or complete.
    """

    SECRET_DIRECTORY_UNSET = "no directory is named for the instance's secrets"
    """
    The environment does not name the directory the key and secrets are kept in.
    """

    ALREADY_REGISTERED = "the secret directory already holds a registered App"
    """
    Registering again would overwrite the key of an App that exists.
    """

    TIMED_OUT = "GitHub did not send the browser back in time"
    """
    The manifest was never submitted, or its registration never completed.
    """


@dataclass
class RegistrationRefused(DataclassException):
    """
    Raised when the App's registration cannot proceed or complete.
    """

    failure: RegistrationFailure
    """
    What refuses it.
    """

    def error_message(self) -> str:
        return f"The App cannot be registered: {self.failure}."

    def suggest_correction(self) -> str:
        match self.failure:
            case RegistrationFailure.SECRET_DIRECTORY_UNSET:
                return f"Set {HubServerVariable.SECRET_DIRECTORY} to a directory."
            case RegistrationFailure.ALREADY_REGISTERED:
                return (
                    "Point the secret directory at an empty one, or delete the App "
                    "on GitHub and empty this directory first."
                )
            case RegistrationFailure.TIMED_OUT:
                return (
                    "Run the command again and finish the registration in the browser."
                )
