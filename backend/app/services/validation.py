from dataclasses import dataclass
from datetime import datetime

from app.models.enums import ReadingQuality
from app.plc.base import TagReadResult
from app.plc.tags import TagDefinition

DIGITAL_TRUE = 1.0
DIGITAL_FALSE = 0.0

#: How far outside a tag's configured engineering span (as a fraction of that span) a value
#: may go before it's judged physically implausible rather than a legitimate excursion.
DEFAULT_RANGE_MARGIN_FRACTION = 0.2

#: How much of a tag's engineering span a value may move across a single poll cycle before
#: it's judged a sensor/wiring fault rather than a real physical change.
DEFAULT_MAX_JUMP_FRACTION = 0.5


@dataclass
class ValidatedReading:
    tag_name: str
    value: float
    quality: ReadingQuality
    timestamp: datetime


@dataclass
class ReadFailure:
    """The read itself failed (decode error, PLC rejected the request) — nothing to store,
    distinct from a successfully-decoded-but-implausible (BAD quality) reading.
    """

    tag_name: str
    error: str
    timestamp: datetime


class ReadingValidator:
    """Sits between the PLC poller and the database (ARCHITECTURE.md §5): range and
    rate-of-change checks on analog tags, straight pass-through for digital tags, and a
    staleness helper for "live status" views. Tracks the last known-good value per tag to
    evaluate rate-of-change, so one instance must be reused across poll cycles, not
    recreated per cycle.
    """

    def __init__(
        self,
        range_margin_fraction: float = DEFAULT_RANGE_MARGIN_FRACTION,
        max_jump_fraction: float = DEFAULT_MAX_JUMP_FRACTION,
    ) -> None:
        self._range_margin_fraction = range_margin_fraction
        self._max_jump_fraction = max_jump_fraction
        self._last_good: dict[str, tuple[float, datetime]] = {}

    def validate(
        self, tag: TagDefinition, result: TagReadResult, timestamp: datetime
    ) -> ValidatedReading | ReadFailure:
        if not result.ok or result.value is None:
            return ReadFailure(tag_name=tag.name, error=result.error or "no value returned", timestamp=timestamp)

        if tag.kind == "digital":
            value = DIGITAL_TRUE if result.value else DIGITAL_FALSE
            self._last_good[tag.name] = (value, timestamp)
            return ValidatedReading(tag.name, value, ReadingQuality.GOOD, timestamp)

        assert tag.scale is not None
        value = float(result.value)
        span = tag.scale.eng_max - tag.scale.eng_min
        quality = ReadingQuality.GOOD

        margin = span * self._range_margin_fraction
        if value < tag.scale.eng_min - margin or value > tag.scale.eng_max + margin:
            quality = ReadingQuality.BAD

        previous = self._last_good.get(tag.name)
        if quality == ReadingQuality.GOOD and previous is not None:
            prev_value, _ = previous
            if abs(value - prev_value) > span * self._max_jump_fraction:
                quality = ReadingQuality.BAD

        if quality == ReadingQuality.GOOD:
            self._last_good[tag.name] = (value, timestamp)

        return ValidatedReading(tag.name, value, quality, timestamp)

    def last_good_timestamp(self, tag_name: str) -> datetime | None:
        entry = self._last_good.get(tag_name)
        return entry[1] if entry else None

    def is_stale(self, tag_name: str, now: datetime, max_age_seconds: float) -> bool:
        """Used by "live status" views (Module 4/5), not written into stored rows — a
        freshly-written reading is by definition not stale; staleness describes a *previous*
        reading having gone quiet, which is a property of the clock, not of any one poll.
        """
        last = self.last_good_timestamp(tag_name)
        if last is None:
            return True
        return (now - last).total_seconds() > max_age_seconds
