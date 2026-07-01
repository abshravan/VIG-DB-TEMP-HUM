import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  createUser,
  deleteUser,
  fetchAlarmRules,
  fetchSensors,
  fetchSettings,
  fetchUsers,
  updateAlarmRule,
  updateSensor,
  updateSettings,
  updateUser,
} from "../api/endpoints";
import { useAuthStore } from "../store/authStore";
import type { AlarmRule, UserRole } from "../types/api";

type Tab = "sensors" | "alarm-rules" | "configuration" | "users";

export function SettingsPage() {
  const role = useAuthStore((state) => state.role);
  const isAdmin = role === "ADMIN";
  const canEditSensors = role === "ADMIN" || role === "OPERATOR";
  const [tab, setTab] = useState<Tab>("sensors");

  return (
    <div className="space-y-6">
      <div className="flex gap-1">
        <TabButton active={tab === "sensors"} onClick={() => setTab("sensors")}>
          Sensors
        </TabButton>
        <TabButton active={tab === "alarm-rules"} onClick={() => setTab("alarm-rules")}>
          Alarm rules
        </TabButton>
        <TabButton active={tab === "configuration"} onClick={() => setTab("configuration")}>
          Configuration
        </TabButton>
        {isAdmin && (
          <TabButton active={tab === "users"} onClick={() => setTab("users")}>
            Users
          </TabButton>
        )}
      </div>

      {tab === "sensors" && <SensorsTab canEdit={canEditSensors} />}
      {tab === "alarm-rules" && <AlarmRulesTab canEdit={isAdmin} />}
      {tab === "configuration" && <ConfigurationTab canEdit={isAdmin} />}
      {tab === "users" && isAdmin && <UsersTab />}
    </div>
  );
}

function SensorsTab({ canEdit }: { canEdit: boolean }) {
  const queryClient = useQueryClient();
  const sensorsQuery = useQuery({ queryKey: ["sensors"], queryFn: fetchSensors });
  const [editing, setEditing] = useState<Record<number, string>>({});

  async function handleSave(sensorId: number) {
    const displayName = editing[sensorId];
    if (displayName === undefined) return;
    await updateSensor(sensorId, { display_name: displayName });
    await queryClient.invalidateQueries({ queryKey: ["sensors"] });
    setEditing((prev) => {
      const next = { ...prev };
      delete next[sensorId];
      return next;
    });
  }

  return (
    <div className="overflow-hidden rounded-lg border border-slate-800">
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-900/60 text-slate-400">
          <tr>
            <th className="px-4 py-2 font-medium">Tag</th>
            <th className="px-4 py-2 font-medium">Display name</th>
            <th className="px-4 py-2 font-medium">Type</th>
            <th className="px-4 py-2 font-medium">Location</th>
            {canEdit && <th className="px-4 py-2" />}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800">
          {sensorsQuery.data?.map((sensor) => (
            <tr key={sensor.id} className="text-slate-200">
              <td className="px-4 py-2 font-mono text-xs text-slate-400">{sensor.tag_name}</td>
              <td className="px-4 py-2">
                {canEdit ? (
                  <input
                    value={editing[sensor.id] ?? sensor.display_name}
                    onChange={(e) => setEditing((prev) => ({ ...prev, [sensor.id]: e.target.value }))}
                    className="rounded-md border border-slate-700 bg-slate-950 px-2 py-1 text-sm"
                  />
                ) : (
                  sensor.display_name
                )}
              </td>
              <td className="px-4 py-2">{sensor.sensor_type}</td>
              <td className="px-4 py-2 text-slate-400">{sensor.location ?? "—"}</td>
              {canEdit && (
                <td className="px-4 py-2 text-right">
                  {editing[sensor.id] !== undefined && (
                    <button
                      type="button"
                      onClick={() => handleSave(sensor.id)}
                      className="rounded-md bg-sky-600 px-2 py-1 text-xs font-medium text-white hover:bg-sky-500"
                    >
                      Save
                    </button>
                  )}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AlarmRulesTab({ canEdit }: { canEdit: boolean }) {
  const queryClient = useQueryClient();
  const rulesQuery = useQuery({ queryKey: ["alarm-rules"], queryFn: fetchAlarmRules });

  async function handleUpdate(rule: AlarmRule, patch: Partial<AlarmRule>) {
    await updateAlarmRule(rule.id, patch);
    await queryClient.invalidateQueries({ queryKey: ["alarm-rules"] });
  }

  return (
    <div className="overflow-hidden rounded-lg border border-slate-800">
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-900/60 text-slate-400">
          <tr>
            <th className="px-4 py-2 font-medium">Type</th>
            <th className="px-4 py-2 font-medium">Threshold</th>
            <th className="px-4 py-2 font-medium">Hysteresis</th>
            <th className="px-4 py-2 font-medium">Debounce (s)</th>
            <th className="px-4 py-2 font-medium">Severity</th>
            <th className="px-4 py-2 font-medium">Enabled</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800">
          {rulesQuery.data?.map((rule) => (
            <tr key={rule.id} className="text-slate-200">
              <td className="px-4 py-2">{rule.alarm_type}</td>
              <td className="px-4 py-2">
                {rule.threshold_value === null ? (
                  "—"
                ) : canEdit ? (
                  <input
                    type="number"
                    defaultValue={rule.threshold_value}
                    onBlur={(e) => handleUpdate(rule, { threshold_value: Number(e.target.value) })}
                    className="w-24 rounded-md border border-slate-700 bg-slate-950 px-2 py-1 text-sm"
                  />
                ) : (
                  rule.threshold_value
                )}
              </td>
              <td className="px-4 py-2 text-slate-400">{rule.hysteresis}</td>
              <td className="px-4 py-2 text-slate-400">{rule.min_duration_seconds}</td>
              <td className="px-4 py-2">{rule.severity}</td>
              <td className="px-4 py-2">
                {canEdit ? (
                  <input
                    type="checkbox"
                    checked={rule.is_enabled}
                    onChange={(e) => handleUpdate(rule, { is_enabled: e.target.checked })}
                  />
                ) : rule.is_enabled ? (
                  "Yes"
                ) : (
                  "No"
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ConfigurationTab({ canEdit }: { canEdit: boolean }) {
  const queryClient = useQueryClient();
  const settingsQuery = useQuery({ queryKey: ["settings"], queryFn: fetchSettings });
  const [values, setValues] = useState<Record<string, string>>({});

  async function handleSave(key: string) {
    const value = values[key];
    if (value === undefined) return;
    await updateSettings({ [key]: value });
    await queryClient.invalidateQueries({ queryKey: ["settings"] });
    setValues((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  }

  return (
    <div className="overflow-hidden rounded-lg border border-slate-800">
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-900/60 text-slate-400">
          <tr>
            <th className="px-4 py-2 font-medium">Key</th>
            <th className="px-4 py-2 font-medium">Value</th>
            {canEdit && <th className="px-4 py-2" />}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800">
          {settingsQuery.data?.map((config) => (
            <tr key={config.key} className="text-slate-200">
              <td className="px-4 py-2 font-mono text-xs text-slate-400">{config.key}</td>
              <td className="px-4 py-2">
                {canEdit ? (
                  <input
                    value={values[config.key] ?? config.value}
                    onChange={(e) => setValues((prev) => ({ ...prev, [config.key]: e.target.value }))}
                    className="rounded-md border border-slate-700 bg-slate-950 px-2 py-1 text-sm"
                  />
                ) : (
                  config.value
                )}
              </td>
              {canEdit && (
                <td className="px-4 py-2 text-right">
                  {values[config.key] !== undefined && (
                    <button
                      type="button"
                      onClick={() => handleSave(config.key)}
                      className="rounded-md bg-sky-600 px-2 py-1 text-xs font-medium text-white hover:bg-sky-500"
                    >
                      Save
                    </button>
                  )}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      {settingsQuery.data?.length === 0 && (
        <p className="px-4 py-6 text-center text-sm text-slate-500">No configuration values seeded yet.</p>
      )}
    </div>
  );
}

function UsersTab() {
  const queryClient = useQueryClient();
  const usersQuery = useQuery({ queryKey: ["users"], queryFn: fetchUsers });
  const [newUsername, setNewUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState<UserRole>("VIEWER");

  async function handleCreate() {
    if (!newUsername || newPassword.length < 8) return;
    await createUser({ username: newUsername, password: newPassword, role: newRole });
    setNewUsername("");
    setNewPassword("");
    await queryClient.invalidateQueries({ queryKey: ["users"] });
  }

  async function handleRoleChange(userId: number, role: UserRole) {
    await updateUser(userId, { role });
    await queryClient.invalidateQueries({ queryKey: ["users"] });
  }

  async function handleToggleActive(userId: number, isActive: boolean) {
    await updateUser(userId, { is_active: isActive });
    await queryClient.invalidateQueries({ queryKey: ["users"] });
  }

  async function handleDelete(userId: number) {
    await deleteUser(userId);
    await queryClient.invalidateQueries({ queryKey: ["users"] });
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3 rounded-lg border border-slate-800 bg-slate-900/60 p-4">
        <input
          placeholder="Username"
          value={newUsername}
          onChange={(e) => setNewUsername(e.target.value)}
          className="rounded-md border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm"
        />
        <input
          placeholder="Password (min 8 chars)"
          type="password"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          className="rounded-md border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm"
        />
        <select
          value={newRole}
          onChange={(e) => setNewRole(e.target.value as UserRole)}
          className="rounded-md border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm"
        >
          <option value="VIEWER">Viewer</option>
          <option value="OPERATOR">Operator</option>
          <option value="ADMIN">Admin</option>
        </select>
        <button
          type="button"
          onClick={handleCreate}
          className="rounded-md bg-sky-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-sky-500"
        >
          Add user
        </button>
      </div>

      <div className="overflow-hidden rounded-lg border border-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-900/60 text-slate-400">
            <tr>
              <th className="px-4 py-2 font-medium">Username</th>
              <th className="px-4 py-2 font-medium">Role</th>
              <th className="px-4 py-2 font-medium">Active</th>
              <th className="px-4 py-2 font-medium">Last login</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {usersQuery.data?.map((user) => (
              <tr key={user.id} className="text-slate-200">
                <td className="px-4 py-2">{user.username}</td>
                <td className="px-4 py-2">
                  <select
                    value={user.role}
                    onChange={(e) => handleRoleChange(user.id, e.target.value as UserRole)}
                    className="rounded-md border border-slate-700 bg-slate-950 px-2 py-1 text-sm"
                  >
                    <option value="VIEWER">Viewer</option>
                    <option value="OPERATOR">Operator</option>
                    <option value="ADMIN">Admin</option>
                  </select>
                </td>
                <td className="px-4 py-2">
                  <input
                    type="checkbox"
                    checked={user.is_active}
                    onChange={(e) => handleToggleActive(user.id, e.target.checked)}
                  />
                </td>
                <td className="px-4 py-2 text-slate-400">
                  {user.last_login_at ? new Date(user.last_login_at).toLocaleString() : "Never"}
                </td>
                <td className="px-4 py-2 text-right">
                  <button
                    type="button"
                    onClick={() => handleDelete(user.id)}
                    className="rounded-md bg-red-600/20 px-2 py-1 text-xs font-medium text-red-400 hover:bg-red-600/30"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-md px-3 py-1.5 text-sm font-medium ${
        active ? "bg-slate-800 text-white" : "text-slate-400 hover:text-slate-200"
      }`}
    >
      {children}
    </button>
  );
}
