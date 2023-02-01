"""
`abi3audit` CLI state, broken out to avoid circular imports.
"""

from __future__ import annotations

import os
import sys
from typing import Literal

from rich.console import Console

# TODO: Remove this once rich's NO_COLOR handling is fixed.
# See: https://github.com/Textualize/rich/issues/2549
_color_system: Literal["auto"] | None
if os.getenv("NO_COLOR", None) is not None:
    _color_system = None
else:
    _color_system = "auto"

console = Console(log_path=False, file=sys.stderr, color_system=_color_system)
status = console.status("[green]Processing inputs", spinner="clock")
