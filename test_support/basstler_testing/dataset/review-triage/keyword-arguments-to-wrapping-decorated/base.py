from __future__ import annotations

from other_markers import called_positionally


class Factory:
    @staticmethod
    @called_positionally
    def create(camera: str, rate: float) -> str:
        return f"{camera} at {rate}"


def default_camera() -> str:
    return Factory.create("kinect", 30.0)
