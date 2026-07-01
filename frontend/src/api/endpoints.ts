import { apiClient } from "./client";
import type {
  Alarm,
  AlarmRule,
  AlarmSeverity,
  AlarmState,
  Configuration,
  HistoryPoint,
  LiveStatus,
  Sensor,
  SensorType,
  SimulationStatus,
  SystemHealth,
  SystemLog,
  TokenResponse,
  User,
  UserRole,
} from "../types/api";

export async function login(username: string, password: string): Promise<TokenResponse> {
  const response = await apiClient.post<TokenResponse>("/auth/login", { username, password });
  return response.data;
}

export async function fetchMe(): Promise<User> {
  const response = await apiClient.get<User>("/auth/me");
  return response.data;
}

export async function fetchLiveStatus(): Promise<LiveStatus> {
  const response = await apiClient.get<LiveStatus>("/live");
  return response.data;
}

export async function fetchSensors(): Promise<Sensor[]> {
  const response = await apiClient.get<Sensor[]>("/sensors");
  return response.data;
}

export async function updateSensor(
  sensorId: number,
  payload: Partial<Pick<Sensor, "display_name" | "location" | "is_active">>,
): Promise<Sensor> {
  const response = await apiClient.patch<Sensor>(`/sensors/${sensorId}`, payload);
  return response.data;
}

export async function createSensor(payload: {
  tag_name: string;
  display_name: string;
  sensor_type: SensorType;
  unit?: string;
  location?: string;
}): Promise<Sensor> {
  const response = await apiClient.post<Sensor>("/sensors", payload);
  return response.data;
}

export interface HistoryParams {
  sensorId: number;
  start: string;
  end: string;
  resolution: "raw" | "hourly" | "daily";
}

export async function fetchHistory({ sensorId, start, end, resolution }: HistoryParams): Promise<HistoryPoint[]> {
  const response = await apiClient.get<HistoryPoint[]>("/history", {
    params: { sensor_id: sensorId, start, end, resolution },
  });
  return response.data;
}

export async function downloadHistoryCsv({ sensorId, start, end, resolution }: HistoryParams): Promise<Blob> {
  const response = await apiClient.get("/history/export", {
    params: { sensor_id: sensorId, start, end, resolution },
    responseType: "blob",
  });
  return response.data;
}

export async function fetchAlarms(filters: {
  state?: AlarmState;
  severity?: AlarmSeverity;
  start?: string;
  end?: string;
}): Promise<Alarm[]> {
  const response = await apiClient.get<Alarm[]>("/alarms", { params: filters });
  return response.data;
}

export async function acknowledgeAlarm(alarmId: number): Promise<Alarm> {
  const response = await apiClient.post<Alarm>(`/alarms/${alarmId}/acknowledge`);
  return response.data;
}

export async function fetchEvents(limit = 100): Promise<SystemLog[]> {
  const response = await apiClient.get<SystemLog[]>("/events", { params: { limit } });
  return response.data;
}

export async function fetchSettings(): Promise<Configuration[]> {
  const response = await apiClient.get<Configuration[]>("/settings");
  return response.data;
}

export async function updateSettings(values: Record<string, string>): Promise<Configuration[]> {
  const response = await apiClient.put<Configuration[]>("/settings", { values });
  return response.data;
}

export async function fetchAlarmRules(): Promise<AlarmRule[]> {
  const response = await apiClient.get<AlarmRule[]>("/settings/alarm-rules");
  return response.data;
}

export async function updateAlarmRule(ruleId: number, payload: Partial<AlarmRule>): Promise<AlarmRule> {
  const response = await apiClient.put<AlarmRule>(`/settings/alarm-rules/${ruleId}`, payload);
  return response.data;
}

export async function fetchUsers(): Promise<User[]> {
  const response = await apiClient.get<User[]>("/users");
  return response.data;
}

export async function createUser(payload: { username: string; password: string; role: UserRole }): Promise<User> {
  const response = await apiClient.post<User>("/users", payload);
  return response.data;
}

export async function updateUser(
  userId: number,
  payload: Partial<{ password: string; role: UserRole; is_active: boolean }>,
): Promise<User> {
  const response = await apiClient.patch<User>(`/users/${userId}`, payload);
  return response.data;
}

export async function deleteUser(userId: number): Promise<void> {
  await apiClient.delete(`/users/${userId}`);
}

export async function fetchSystemHealth(): Promise<SystemHealth> {
  const response = await apiClient.get<SystemHealth>("/system/health");
  return response.data;
}

export async function fetchSimulationStatus(): Promise<SimulationStatus> {
  const response = await apiClient.get<SimulationStatus>("/system/simulate");
  return response.data;
}

export async function setSimulatedTagValue(tagName: string, value: number | boolean): Promise<void> {
  await apiClient.put(`/system/simulate/tags/${tagName}`, { value });
}

export async function setSimulatedTagFailure(tagName: string, failing: boolean): Promise<void> {
  await apiClient.put(`/system/simulate/tags/${tagName}/failure`, { failing });
}

export async function setSimulatedPlcConnection(disconnected: boolean): Promise<void> {
  await apiClient.put("/system/simulate/plc-connection", { disconnected });
}
