from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ConfigurationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    value: str
    value_type: str
    updated_at: datetime


class ConfigurationUpdate(BaseModel):
    value: str


class ConfigurationBulkUpdate(BaseModel):
    """Body for `PUT /settings`: `{"values": {"poll_interval_seconds": "5", ...}}`.
    Unknown keys are silently ignored rather than auto-creating new Configuration rows —
    the set of valid keys is fixed by what's seeded, not client-defined.
    """

    values: dict[str, str]
