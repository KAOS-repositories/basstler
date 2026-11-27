"""
Run the hub server's commands with ``python -m basstler.hub_server``.
"""

from __future__ import annotations

from basstler.hub_server.command_line import hub_server_app

if __name__ == "__main__":
    hub_server_app()
