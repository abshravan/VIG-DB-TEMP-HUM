# config/

Runtime configuration that comes from the PLC team or an operator, not from developers — kept out of application code so the PLC's tag layout or protocol choice never requires a code change. See [ARCHITECTURE.md §4.2](../docs/architecture/ARCHITECTURE.md#42-tag-map-configplc_tagsyaml).

| File (to be added) | Purpose |
|---|---|
| `plc_tags.yaml` | The tag map handed to us by the PLC team: logical sensor name → S7 DB/offset or Modbus register, data type, scaling (raw-to-engineering), and poll tier (fast/normal). |
| `alarm_rules.example.yaml` | Example default alarm thresholds/hysteresis/debounce/severity, used to seed the `AlarmRule` table on first setup. |
