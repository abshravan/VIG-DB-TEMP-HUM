import random

from app.plc.base import PLCClient, TagReadResult
from app.plc.tags import TagDefinition


class SimulatedPLCClient(PLCClient):
    """In-process fake PLC, implementing the same `PLCClient` interface as the real S7/Modbus
    clients. Used for development and automated tests before real PLC network access is
    available (ARCHITECTURE.md §17, Module 2) — the poller, validation layer, and alarm engine
    all exercise identical code paths against this as against real hardware.

    Selected at runtime via `PLC_PROTOCOL=simulated` (`app/plc/factory.py`); the `set_*`
    methods below are then reachable at runtime through the admin-only
    `/api/v1/system/simulate` endpoints (`app/api/v1/system.py`) so an operator can drive
    specific scenarios (a temperature spike, a stuck sensor, a PLC that drops off the network)
    without any hardware.
    """

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)
        self._connected = False
        self._values: dict[str, float | bool] = {}
        self._force_disconnected = False
        self._failing_tags: set[str] = set()

    async def connect(self) -> None:
        if self._force_disconnected:
            raise ConnectionError("simulated PLC unreachable")
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def set_force_disconnected(self, disconnected: bool) -> None:
        """Simulate the PLC going offline, or coming back."""
        self._force_disconnected = disconnected
        if disconnected:
            self._connected = False

    def set_tag_failing(self, tag_name: str, failing: bool) -> None:
        """Simulate a single sensor/wiring fault without taking down the whole PLC."""
        if failing:
            self._failing_tags.add(tag_name)
        else:
            self._failing_tags.discard(tag_name)

    def set_value(self, tag_name: str, value: float | bool) -> None:
        """Pin a tag to an exact value (e.g. to trigger an alarm threshold). Used by tests and
        by the admin simulation API (`/api/v1/system/simulate`, PLC_PROTOCOL=simulated).
        """
        self._values[tag_name] = value

    def get_value(self, tag_name: str) -> float | bool | None:
        """Current pinned/drifted value for a tag, or `None` if it hasn't been read yet."""
        return self._values.get(tag_name)

    def is_tag_failing(self, tag_name: str) -> bool:
        return tag_name in self._failing_tags

    async def read_tags(self, tags: list[TagDefinition]) -> dict[str, TagReadResult]:
        if not self._connected:
            raise ConnectionError("not connected")
        results: dict[str, TagReadResult] = {}
        for tag in tags:
            if tag.name in self._failing_tags:
                results[tag.name] = TagReadResult(value=None, ok=False, error="simulated sensor failure")
                continue
            results[tag.name] = TagReadResult(value=self._value_for(tag), ok=True)
        return results

    def _value_for(self, tag: TagDefinition) -> float | bool:
        current = self._values.get(tag.name)
        if current is None:
            if tag.kind == "digital":
                current = False
            else:
                assert tag.scale is not None
                current = (tag.scale.eng_min + tag.scale.eng_max) / 2
        elif tag.kind == "analog" and isinstance(current, (int, float)):
            assert tag.scale is not None
            drift = self._rng.uniform(-0.2, 0.2)
            current = min(max(current + drift, tag.scale.eng_min), tag.scale.eng_max)
        self._values[tag.name] = current
        return current
