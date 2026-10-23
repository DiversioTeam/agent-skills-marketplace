"""The harness-neutral transcript model every parser produces and the renderer reads."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

TurnKind = Literal["developer", "teammate", "agent", "compaction"]


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict[str, object]
    timestamp: str = ""
    output: str | None = None
    is_error: bool = False
    # Why the output (and file contents in the input) are not published, if they are not.
    withheld: str | None = None
    # A subagent this call started, rendered nested at the call site.
    subagent: Unit | None = None


@dataclass
class Item:
    kind: Literal["assistant", "tool", "note"]
    text: str = ""
    tool: ToolCall | None = None
    timestamp: str = ""


@dataclass
class Turn:
    kind: TurnKind
    text: str
    timestamp: str
    items: list[Item] = field(default_factory=list)
    # Who sent a teammate or agent message, when known.
    sender: str = ""
    # The page-wide number shown in the preview and used by --drop-turn and --include-output.
    number: int = 0
    # Set while parsing: did this turn mention the branch or PR, and which branch was checked out.
    evidence: bool = False
    branch: str = ""


@dataclass
class Tokens:
    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0

    def add(self, other: Tokens) -> None:
        self.input += other.input
        self.output += other.output
        self.cache_read += other.cache_read
        self.cache_write += other.cache_write

    @property
    def total(self) -> int:
        return self.input + self.output + self.cache_read + self.cache_write


@dataclass
class Unit:
    """One transcript file: a session's main thread, a subagent, or an agent-team teammate."""

    id: str
    harness: str
    kind: Literal["session", "subagent", "teammate"]
    title: str
    session_id: str
    path: str
    cwd: str = ""
    models: list[str] = field(default_factory=list)
    started: str = ""
    ended: str = ""
    tokens: Tokens = field(default_factory=Tokens)
    turns: list[Turn] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    parent_tool_use_id: str = ""
    teammates: list[Unit] = field(default_factory=list)
    # Turns left out because they were about other work; shown as a gap note.
    omitted_turns: int = 0
