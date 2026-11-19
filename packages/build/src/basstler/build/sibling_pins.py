"""
A hatch metadata hook pinning a distribution's basstler requirements to its own version,
so every basstler distribution of one release installs together.
"""

from __future__ import annotations

from typing import Any

from hatchling.metadata.plugin.interface import MetadataHookInterface
from hatchling.plugin import hookimpl
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import Version

# %% the hook


class SiblingPinsHook(MetadataHookInterface):
    """
    Sets the distribution's dependencies to the hook's ``dependencies`` setting, each
    requirement of a basstler distribution pinned to the version being built.

    A distribution lists the hook as ``[tool.hatch.metadata.hooks.basstler-sibling-pins]``
    and names ``dependencies`` in ``project.dynamic``.
    """

    PLUGIN_NAME = "basstler-sibling-pins"
    """
    The name a ``pyproject.toml`` configures the hook under.
    """

    family = "basstler"
    """
    The distribution whose name, alone or followed by a hyphen and a part, names a
    sibling.
    """

    def update(self, metadata: dict[str, Any]) -> None:
        """
        :param metadata: The distribution's metadata, its version already set; its
            ``dependencies`` are replaced.
        """
        version = Version(metadata["version"])
        metadata["dependencies"] = [
            str(self.pinned(Requirement(specifier), version))
            for specifier in self.config.get("dependencies", [])
        ]

    def pinned(self, requirement: Requirement, version: Version) -> Requirement:
        """
        :param requirement: One requirement of the distribution.
        :param version: The version being built.
        :return: *requirement*, its markers and extras kept, pinned to *version* when it
            names a sibling; else *requirement* itself.
        """
        name = canonicalize_name(requirement.name)
        if name != self.family and not name.startswith(f"{self.family}-"):
            return requirement
        pinned = Requirement(str(requirement))
        pinned.specifier = SpecifierSet(f"=={version}")
        return pinned


@hookimpl
def hatch_register_metadata_hook() -> type[MetadataHookInterface]:
    """
    :return: The hook, for hatch to find by its :attr:`SiblingPinsHook.PLUGIN_NAME`.
    """
    return SiblingPinsHook
