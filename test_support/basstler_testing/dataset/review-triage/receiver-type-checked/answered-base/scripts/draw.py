"""
Draws a trajectory with a plotter from an annotated factory.
"""

from __future__ import annotations

from plotting.plotters import annotated_trajectory_plotter

annotated_trajectory_plotter().plot("trajectory.pdf")
