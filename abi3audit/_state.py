"""
`abi3audit` CLI state, broken out to avoid circular imports.
"""

from __future__ import annotations

import os
import sys
from typing import Literal

from rich.console import Console


class Status(object):
    def __init__(self, console: Console):
        self._console = console
        self._status = None

    def __enter__(self):
        if self._status:
            self._status.__enter__()
        return self

    def __exit__(self, *args):
        if self._status:
            self._status.__exit__(*args)

    def initiate(self):
        self._status = self._console.status("[green]Processing inputs", spinner="clock")

    def update(self, s: str):
        if self._status:
            self._status.update(s)


# TODO: Remove this once rich's NO_COLOR handling is fixed.
# See: https://github.com/Textualize/rich/issues/2549
_color_system: Literal["auto"] | None
if os.getenv("NO_COLOR", None) is not None:
    _color_system = None
else:
    _color_system = "auto"

console = Console(log_path=False, file=sys.stderr, color_system=_color_system)
status = Status(console)
