from datetime import datetime, timedelta

from app.models.enums import ReadingQuality
from app.plc.base import TagReadResult
from app.plc.tags import TagDefinition
from app.services.validation import ReadFailure, ReadingValidator, ValidatedReading

ANALOG_TAG = TagDefinition(
    name="temp_a",
    kind="analog",
    sensor_type="TEMPERATURE",
    poll_tier="normal",
    s7={"db": 1, "offset": 0, "type": "REAL"},
    scale={"raw_min": 0, "raw_max": 100, "eng_min": 0, "eng_max": 50, "unit": "°C"},
)
DIGITAL_TAG = TagDefinition(
    name="door_a",
    kind="digital",
    sensor_type="DOOR",
    poll_tier="fast",
    s7={"db": 1, "offset": 8, "type": "BOOL", "bit": 0},
)

T0 = datetime(2026, 1, 1, 12, 0, 0)


def test_failed_read_produces_read_failure():
    validator = ReadingValidator()
    outcome = validator.validate(ANALOG_TAG, TagReadResult(value=None, ok=False, error="timeout"), T0)
    assert isinstance(outcome, ReadFailure)
    assert outcome.error == "timeout"


def test_digital_reading_always_good():
    validator = ReadingValidator()
    outcome = validator.validate(DIGITAL_TAG, TagReadResult(value=True, ok=True), T0)
    assert isinstance(outcome, ValidatedReading)
    assert outcome.value == 1.0
    assert outcome.quality == ReadingQuality.GOOD


def test_analog_reading_within_span_is_good():
    validator = ReadingValidator()
    outcome = validator.validate(ANALOG_TAG, TagReadResult(value=25.0, ok=True), T0)
    assert isinstance(outcome, ValidatedReading)
    assert outcome.quality == ReadingQuality.GOOD
    assert outcome.value == 25.0


def test_analog_reading_far_outside_span_is_bad():
    # span is 0-50, 20% margin -> plausible up to 60; 200 is far beyond that
    validator = ReadingValidator()
    outcome = validator.validate(ANALOG_TAG, TagReadResult(value=200.0, ok=True), T0)
    assert isinstance(outcome, ValidatedReading)
    assert outcome.quality == ReadingQuality.BAD


def test_analog_reading_within_margin_of_span_is_good():
    # 50 (max) + 15% of 50-span = 57.5, still within the 20% margin -> GOOD
    validator = ReadingValidator()
    outcome = validator.validate(ANALOG_TAG, TagReadResult(value=57.0, ok=True), T0)
    assert outcome.quality == ReadingQuality.GOOD


def test_large_jump_between_cycles_is_bad():
    validator = ReadingValidator()
    first = validator.validate(ANALOG_TAG, TagReadResult(value=20.0, ok=True), T0)
    assert first.quality == ReadingQuality.GOOD

    # span is 50, max jump fraction 0.5 -> anything past a 25-unit jump in one cycle is BAD
    second = validator.validate(ANALOG_TAG, TagReadResult(value=48.0, ok=True), T0 + timedelta(seconds=5))
    assert second.quality == ReadingQuality.BAD


def test_bad_reading_does_not_update_last_known_good():
    validator = ReadingValidator()
    validator.validate(ANALOG_TAG, TagReadResult(value=20.0, ok=True), T0)
    validator.validate(ANALOG_TAG, TagReadResult(value=200.0, ok=True), T0 + timedelta(seconds=5))

    # a subsequent small, plausible move from the *last good* value (20) should still be fine
    outcome = validator.validate(ANALOG_TAG, TagReadResult(value=22.0, ok=True), T0 + timedelta(seconds=10))
    assert outcome.quality == ReadingQuality.GOOD


def test_is_stale_true_before_any_reading():
    validator = ReadingValidator()
    assert validator.is_stale(ANALOG_TAG.name, T0, max_age_seconds=30) is True


def test_is_stale_false_shortly_after_a_good_reading():
    validator = ReadingValidator()
    validator.validate(ANALOG_TAG, TagReadResult(value=20.0, ok=True), T0)
    assert validator.is_stale(ANALOG_TAG.name, T0 + timedelta(seconds=5), max_age_seconds=30) is False


def test_is_stale_true_long_after_last_good_reading():
    validator = ReadingValidator()
    validator.validate(ANALOG_TAG, TagReadResult(value=20.0, ok=True), T0)
    assert validator.is_stale(ANALOG_TAG.name, T0 + timedelta(seconds=60), max_age_seconds=30) is True
