"""
`abi3audit` CLI state, broken out to avoid circular imports.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Literal, Optional, Type
from types import TracebackType

from rich.console import Console
from rich.status import Status


class StatusWrapper:
    _status: Status | None
    def __init__(self, console: Console) -> None:
        self._console = console
        self._status = None

    def __enter__(self) -> StatusWrapper:
        if self._status:
            self._status.__enter__()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> Any:
        if self._status:
            return self._status.__exit__(exc_type, exc_val, exc_tb)
        return False

    def initiate(self) -> None:
        self._status = self._console.status("[green]Processing inputs", spinner="clock")

    def update(self, s: str) -> None:
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
status = StatusWrapper(console)
