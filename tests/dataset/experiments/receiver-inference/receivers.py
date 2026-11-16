from __future__ import annotations

from typing import reveal_type

from pkg.model import Plotter, registry


def run(plotters: list[Plotter]) -> None:
    reveal_type(plotters)
    registry.find("ä").plot(name="x")
    for plotter in plotters:
        plotter.plot(name="y")
