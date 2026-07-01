// Mirrors backend/app/schemas/*.py and backend/app/models/enums.py — kept in one file since
// the whole API surface is small enough that a generated client would be overkill.

export type SensorType = "TEMPERATURE" | "HUMIDITY" | "SMOKE" | "WATER_LEAK" | "DOOR" | "CUSTOM";
export type ReadingQuality = "GOOD" | "BAD" | "STALE";
export type AlarmType =
  | "TEMP_HIGH"
  | "TEMP_LOW"
  | "HUMIDITY_HIGH"
  | "HUMIDITY_LOW"
  | "SMOKE"
  | "DOOR_OPEN"
  | "WATER_LEAK"
  | "PLC_OFFLINE"
  | "SENSOR_FAILURE";
export type AlarmSeverity = "INFO" | "WARNING" | "CRITICAL";
export type AlarmState = "ACTIVE" | "ACKNOWLEDGED" | "CLEARED";
export type UserRole = "ADMIN" | "OPERATOR" | "VIEWER";
export type LogLevel = "INFO" | "WARNING" | "ERROR" | "CRITICAL";
export type LogCategory =
  | "PLC_CONNECTION"
  | "SYSTEM_RESTART"
  | "AUTH"
  | "CONFIG_CHANGE"
  | "BACKUP";

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface User {
  id: number;
  username: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface Sensor {
  id: number;
  tag_name: string;
  display_name: string;
  sensor_type: SensorType;
  unit: string | null;
  location: string | null;
  is_active: boolean;
}

export interface LiveSensor {
  sensor_id: number;
  tag_name: string;
  display_name: string;
  sensor_type: string;
  unit: string | null;
  value: number | null;
  quality: ReadingQuality | null;
  timestamp: string | null;
  is_stale: boolean;
}

export interface LiveStatus {
  plc_connected: boolean;
  sensors: LiveSensor[];
  active_alarm_count: number;
  server_time: string;
}

export interface HistoryPoint {
  timestamp: string;
  value: number;
  quality: ReadingQuality;
}

export interface Alarm {
  id: number;
  rule_id: number;
  sensor_id: number | null;
  alarm_type: AlarmType;
  severity: AlarmSeverity;
  state: AlarmState;
  triggered_value: number | null;
  triggered_at: string;
  acknowledged_at: string | null;
  acknowledged_by: number | null;
  cleared_at: string | null;
  message: string | null;
}

export interface AlarmRule {
  id: number;
  sensor_id: number | null;
  alarm_type: AlarmType;
  threshold_value: number | null;
  hysteresis: number;
  min_duration_seconds: number;
  severity: AlarmSeverity;
  is_enabled: boolean;
}

export interface SystemLog {
  id: number;
  timestamp: string;
  level: LogLevel;
  category: LogCategory;
  message: string;
  meta: string | null;
}

export interface Configuration {
  key: string;
  value: string;
  value_type: string;
  updated_at: string;
}

export interface SystemHealth {
  cpu_percent: number;
  memory_percent: number;
  disk_percent: number;
  database_size_bytes: number;
  uptime_seconds: number;
  plc_connected: boolean;
  server_time: string;
}

// WebSocket envelope, ARCHITECTURE.md §7.
export type WsMessage =
  | { type: "reading"; data: { timestamp: string; readings: WsReading[] } }
  | { type: "alarm"; data: Alarm }
  | { type: "plc_status"; data: { connected: boolean; state: string } }
  | { type: "system_health"; data: SystemHealth };

export interface WsReading {
  sensor_id: number;
  tag_name: string;
  value: number;
  quality: ReadingQuality;
}
