from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum


class Layer(IntEnum):
    CORE = 1
    LOCAL_TOOLS = 2
    META_PACKAGE = 9


class Distribution(StrEnum):
    CORE = "basstler-core"
    GIT = "basstler-git"
    META_PACKAGE = "basstler"


@dataclass(frozen=True)
class DistributionDeclaration:
    distribution: Distribution
    layer: Layer
    modules: tuple[str, ...]
    dependencies: tuple[Distribution, ...] = ()


PACKAGE_MAP = (
    DistributionDeclaration(
        Distribution.CORE, Layer.CORE, ("bash", "locations", "package_map")
    ),
    DistributionDeclaration(
        Distribution.GIT, Layer.LOCAL_TOOLS, ("git",), (Distribution.CORE,)
    ),
    DistributionDeclaration(
        Distribution.META_PACKAGE,
        Layer.META_PACKAGE,
        ("__main__",),
        (Distribution.CORE, Distribution.GIT),
    ),
)
