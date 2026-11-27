from __future__ import annotations

from other_records import recorded


class Drawer:
    @recorded
    def add(self, part: str, *, field_name: str = "") -> None:
        self.parts.append(part)


def assemble(drawer: Drawer) -> None:
    drawer.add(part="handle")
