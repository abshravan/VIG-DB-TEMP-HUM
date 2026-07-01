import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.plc.tags import TagDefinition


class ConnectionState(str, enum.Enum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    ERROR = "ERROR"


@dataclass
class TagReadResult:
    """Outcome of reading a single tag. `ok=False` means the read itself failed
    (bad decode, PLC rejected the request, timeout) — distinct from the Validation
    Layer's later GOOD/BAD/STALE quality judgement on a successfully-read value.
    """

    value: float | bool | None
    ok: bool
    error: str | None = None


class PLCClient(ABC):
    """Common interface for both protocol implementations (S7PLCClient, ModbusPLCClient).
    Everything above this layer — the poller, validation, alarms — depends only on this
    interface, so the PLC team's protocol choice is a config value, not a rewrite.
    See ARCHITECTURE.md §3.1 and §4.1.
    """

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def read_tags(self, tags: list[TagDefinition]) -> dict[str, TagReadResult]:
        """Read every given tag. Never raises for an individual tag failure — that's
        reported per-tag via `TagReadResult.ok`/`error` so one bad point doesn't blank
        out the whole scan.
        """

    @abstractmethod
    def is_connected(self) -> bool: ...
