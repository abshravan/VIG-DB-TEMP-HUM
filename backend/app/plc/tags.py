from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, model_validator

from app.models.enums import SensorType


class S7TagAddress(BaseModel):
    """See ARCHITECTURE.md §3.1: the target DB must have "Optimized block access"
    unchecked so these byte offsets stay stable.
    """

    db: int
    offset: int
    type: Literal["REAL", "INT", "BOOL"] = "REAL"
    bit: int | None = None  # required when type == "BOOL"


class ModbusTagAddress(BaseModel):
    register_address: int
    type: Literal["FLOAT32", "INT16", "COIL"] = "FLOAT32"


class ScaleConfig(BaseModel):
    """Linear raw-to-engineering conversion for analog tags (e.g. 0-27648 raw -> 0-50 °C)."""

    raw_min: float
    raw_max: float
    eng_min: float
    eng_max: float
    unit: str


class TagDefinition(BaseModel):
    name: str
    kind: Literal["analog", "digital"]
    sensor_type: SensorType
    poll_tier: Literal["fast", "normal"]
    s7: S7TagAddress | None = None
    modbus: ModbusTagAddress | None = None
    scale: ScaleConfig | None = None

    @model_validator(mode="after")
    def _validate_kind_consistency(self) -> "TagDefinition":
        if self.kind == "analog" and self.scale is None:
            raise ValueError(f"tag {self.name!r}: analog tags require a scale block")
        if self.kind == "digital" and self.scale is not None:
            raise ValueError(f"tag {self.name!r}: digital tags must not define a scale block")
        if self.s7 is not None and self.s7.type == "BOOL" and self.s7.bit is None:
            raise ValueError(f"tag {self.name!r}: S7 BOOL address requires 'bit'")
        if self.s7 is None and self.modbus is None:
            raise ValueError(f"tag {self.name!r}: must define at least one of s7/modbus")
        return self


class PollIntervals(BaseModel):
    fast: float = 1.0
    normal: float = 5.0


class TagMap(BaseModel):
    poll_intervals: PollIntervals = PollIntervals()
    tags: list[TagDefinition]

    def tags_for_tier(self, tier: Literal["fast", "normal"]) -> list[TagDefinition]:
        return [t for t in self.tags if t.poll_tier == tier]


def load_tag_map(path: str | Path) -> TagMap:
    """Parse `config/plc_tags.yaml`, handed to us by the PLC team — no code changes needed
    when they add/rename/rewire a tag, only this file.
    """
    with open(path) as f:
        raw = yaml.safe_load(f)
    return TagMap.model_validate(raw)
