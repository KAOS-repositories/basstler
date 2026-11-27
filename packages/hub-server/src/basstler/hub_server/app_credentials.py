"""
What GitHub hands over when the App's manifest is converted.
"""

from __future__ import annotations

from basstler.json_model import ValidatedJSONModel


class AppCredentials(ValidatedJSONModel):
    """
    The identity, key and secrets of a registered App.
    """

    id: int
    """
    The App's numeric identifier.
    """

    slug: str
    """
    The App's name as it appears in its address.
    """

    client_id: str
    """
    The identifier of the App's OAuth client.
    """

    client_secret: str
    """
    The secret of the App's OAuth client.
    """

    webhook_secret: str
    """
    The secret GitHub signs each webhook delivery with.
    """

    pem: str
    """
    The App's private key, in PEM form.
    """
