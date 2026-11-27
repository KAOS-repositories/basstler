from __future__ import annotations

from other_records import recorded


@recorded
def create(name: str, rate: float) -> str:
    return f"{name} at {rate}"


def default_camera() -> str:
    return create(name="kinect", rate=30.0)
