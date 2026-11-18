from __future__ import annotations

from typing import reveal_type

from pkg.model import Plotter, registry


def run(plotters: list[Plotter]) -> None:
    reveal_type(plotters)
    reveal_type(reveal_type(registry).find("ä")).plot(name="x")
    for plotter in plotters:
        reveal_type(plotter).plot(name="y")
