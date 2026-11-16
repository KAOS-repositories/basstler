"""
Draws a trajectory with a plotter from an unannotated factory.
"""

from __future__ import annotations

from plotting.plotters import trajectory_plotter

trajectory_plotter().plot(file_name="trajectory.pdf")
