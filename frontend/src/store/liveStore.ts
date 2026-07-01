import { create } from "zustand";
import type { LiveSensor, LiveStatus, SystemHealth, WsMessage } from "../types/api";

interface LiveState {
  sensors: Record<number, LiveSensor>;
  plcConnected: boolean;
  activeAlarmCount: number;
  systemHealth: SystemHealth | null;
  lastUpdate: string | null;
  hydrate: (status: LiveStatus) => void;
  applyWsMessage: (message: WsMessage) => void;
}

export const useLiveStore = create<LiveState>()((set, get) => ({
  sensors: {},
  plcConnected: false,
  activeAlarmCount: 0,
  systemHealth: null,
  lastUpdate: null,

  hydrate: (status) => {
    const sensors: Record<number, LiveSensor> = {};
    for (const sensor of status.sensors) {
      sensors[sensor.sensor_id] = sensor;
    }
    set({
      sensors,
      plcConnected: status.plc_connected,
      activeAlarmCount: status.active_alarm_count,
      lastUpdate: status.server_time,
    });
  },

  applyWsMessage: (message) => {
    if (message.type === "reading") {
      const sensors = { ...get().sensors };
      for (const reading of message.data.readings) {
        const existing = sensors[reading.sensor_id];
        sensors[reading.sensor_id] = existing
          ? { ...existing, value: reading.value, quality: reading.quality, timestamp: message.data.timestamp, is_stale: false }
          : {
              sensor_id: reading.sensor_id,
              tag_name: reading.tag_name,
              display_name: reading.tag_name,
              sensor_type: "CUSTOM",
              unit: null,
              value: reading.value,
              quality: reading.quality,
              timestamp: message.data.timestamp,
              is_stale: false,
            };
      }
      set({ sensors, lastUpdate: message.data.timestamp });
    } else if (message.type === "alarm") {
      const delta = message.data.state === "ACTIVE" ? 1 : message.data.state === "CLEARED" ? -1 : 0;
      if (delta !== 0) {
        set({ activeAlarmCount: Math.max(0, get().activeAlarmCount + delta) });
      }
    } else if (message.type === "plc_status") {
      set({ plcConnected: message.data.connected });
    } else if (message.type === "system_health") {
      set({ systemHealth: message.data });
    }
  },
}));
