from pathlib import Path

import pytest
from pydantic import ValidationError

from app.plc.tags import TagMap, load_tag_map

REPO_TAG_MAP = Path(__file__).resolve().parents[3] / "config" / "plc_tags.yaml"


def test_load_real_tag_map_from_config():
    tag_map = load_tag_map(REPO_TAG_MAP)
    names = {t.name for t in tag_map.tags}
    assert names == {
        "temp_rack_a",
        "humidity_room",
        "smoke_main",
        "water_leak_floor",
        "door_main",
    }
    assert tag_map.poll_intervals.fast == 1.0
    assert tag_map.poll_intervals.normal == 5.0


def test_tags_for_tier_splits_fast_and_normal():
    tag_map = load_tag_map(REPO_TAG_MAP)
    fast_names = {t.name for t in tag_map.tags_for_tier("fast")}
    normal_names = {t.name for t in tag_map.tags_for_tier("normal")}
    assert fast_names == {"smoke_main", "water_leak_floor", "door_main"}
    assert normal_names == {"temp_rack_a", "humidity_room"}


def test_analog_tag_without_scale_is_rejected():
    with pytest.raises(ValidationError, match="require a scale"):
        TagMap.model_validate(
            {
                "tags": [
                    {
                        "name": "bad_analog",
                        "kind": "analog",
                        "sensor_type": "TEMPERATURE",
                        "poll_tier": "normal",
                        "s7": {"db": 1, "offset": 0, "type": "REAL"},
                    }
                ]
            }
        )


def test_digital_tag_with_scale_is_rejected():
    with pytest.raises(ValidationError, match="must not define a scale"):
        TagMap.model_validate(
            {
                "tags": [
                    {
                        "name": "bad_digital",
                        "kind": "digital",
                        "sensor_type": "DOOR",
                        "poll_tier": "fast",
                        "s7": {"db": 1, "offset": 0, "type": "BOOL", "bit": 0},
                        "scale": {"raw_min": 0, "raw_max": 1, "eng_min": 0, "eng_max": 1, "unit": "x"},
                    }
                ]
            }
        )


def test_s7_bool_without_bit_is_rejected():
    with pytest.raises(ValidationError, match="requires 'bit'"):
        TagMap.model_validate(
            {
                "tags": [
                    {
                        "name": "bad_bool",
                        "kind": "digital",
                        "sensor_type": "SMOKE",
                        "poll_tier": "fast",
                        "s7": {"db": 1, "offset": 0, "type": "BOOL"},
                    }
                ]
            }
        )


def test_tag_with_no_address_is_rejected():
    with pytest.raises(ValidationError, match="must define at least one"):
        TagMap.model_validate(
            {
                "tags": [
                    {
                        "name": "no_address",
                        "kind": "digital",
                        "sensor_type": "DOOR",
                        "poll_tier": "fast",
                    }
                ]
            }
        )
