"""Withholding that follows output to where it is read later.

A withheld call's output can come back through another call: Claude Code's TaskOutput or a read of a background task's
output file, or Pi's read of the full-output file its bash tool writes when output is truncated. Each parser records the
handles a call leaves behind (task ids, output paths) with that call's withholding reason; a later call that names a
handle inherits the reason. A reader of background output whose origin is unknown is withheld.
"""

from __future__ import annotations

import json

from session_model import ToolCall

# Tools whose output is another call's background output.
BACKGROUND_READERS = {"TaskOutput", "BashOutput", "AgentOutputTool"}


class Provenance:
    def __init__(self) -> None:
        self.handles: dict[str, str | None] = {}

    def record(self, handles: list[str], reason: str | None) -> None:
        for handle in handles:
            if handle:
                self.handles[handle] = reason

    def inherited(self, call: ToolCall) -> str | None:
        flat = json.dumps(call.input, default=str)
        reasons = [reason for handle, reason in self.handles.items() if handle in flat]
        if reasons:
            return next((reason for reason in reasons if reason), None)
        return "background output of unknown origin" if call.name in BACKGROUND_READERS else None
