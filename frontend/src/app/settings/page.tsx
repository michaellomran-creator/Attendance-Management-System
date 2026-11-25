"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Copy, MonitorSmartphone, Plus } from "lucide-react";
import { AppShell } from "@/components/ui/AppShell";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ApiError, apiFetch } from "@/lib/api";

interface Department {
  id: string;
  name: string;
  code: string | null;
}

interface Location {
  id: string;
  name: string;
  code: string | null;
}

interface Terminal {
  id: string;
  name: string;
  device_identifier: string;
  location_name: string | null;
  is_active: boolean;
}

interface OrgSettings {
  default_grace_period_minutes: number;
  default_expected_work_minutes: number;
  break_tracking_enabled: boolean;
  overtime_enabled: boolean;
  overtime_requires_approval: boolean;
  terminal_reset_delay_seconds: number;
}

export default function OrganizationSettingsPage() {
  const [departments, setDepartments] = useState<Department[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [terminals, setTerminals] = useState<Terminal[]>([]);
  const [settings, setSettings] = useState<OrgSettings | null>(null);
  const [newTerminalToken, setNewTerminalToken] = useState<string | null>(null);

  const [deptName, setDeptName] = useState("");
  const [locName, setLocName] = useState("");
  const [termName, setTermName] = useState("");
  const [termDevice, setTermDevice] = useState("");
  const [termLocation, setTermLocation] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [savedMsg, setSavedMsg] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
    try {
      const [d, l, t, s] = await Promise.all([
        apiFetch<Department[]>("/organizations/departments"),
        apiFetch<Location[]>("/organizations/locations"),
        apiFetch<Terminal[]>("/terminals"),
        apiFetch<OrgSettings>("/organizations/settings"),
      ]);
      setDepartments(d);
      setLocations(l);
      setTerminals(t);
      setSettings(s);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load settings");
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const handleAddDept = async (e: React.FormEvent) => {
    e.preventDefault();
    await apiFetch("/organizations/departments", {
      method: "POST",
      body: JSON.stringify({ name: deptName }),
    });
    setDeptName("");
    await loadAll();
  };

  const handleAddLocation = async (e: React.FormEvent) => {
    e.preventDefault();
    await apiFetch("/organizations/locations", {
      method: "POST",
      body: JSON.stringify({ name: locName }),
    });
    setLocName("");
    await loadAll();
  };

  const handleAddTerminal = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const res = await apiFetch<Terminal & { terminal_token: string }>("/terminals", {
        method: "POST",
        body: JSON.stringify({
          name: termName,
          device_identifier: termDevice,
          location_id: termLocation || null,
        }),
      });
      setNewTerminalToken(res.terminal_token);
      setTermName("");
      setTermDevice("");
      await loadAll();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to register terminal");
    }
  };

  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!settings) return;
    setSavedMsg(null);
    await apiFetch("/organizations/settings", {
      method: "PATCH",
      body: JSON.stringify(settings),
    });
    setSavedMsg("Attendance policies updated.");
  };

  return (
    <AppShell
      title="Organization Settings"
      subtitle="Manage departments, locations, kiosk terminals, and attendance policies"
    >
      {error && (
        <div className="mb-4 p-3 rounded bg-red-50 border border-red-200 text-xs text-red-800">
          {error}
        </div>
      )}
      {savedMsg && (
        <div className="mb-4 p-3 rounded bg-emerald-50 border border-emerald-200 text-xs text-emerald-900">
          {savedMsg}
        </div>
      )}

      {newTerminalToken && (
        <div className="mb-6 p-4 rounded-lg bg-[#0F3D3E] text-white border border-[#1A5658]">
          <div className="text-sm font-semibold text-[#FFD400] mb-1">
            Terminal Registered — Copy Token Now
          </div>
          <p className="text-xs text-[#D7E4E4] mb-2">
            Use this token on the kiosk device at <code>/terminal</code>. It will not be shown again.
          </p>
          <div className="flex items-center gap-2 bg-[#0A2B2C] p-2.5 rounded font-mono text-xs">
            <span className="flex-1 break-all">{newTerminalToken}</span>
            <button
              onClick={() => navigator.clipboard.writeText(newTerminalToken)}
              className="px-2.5 py-1 rounded bg-[#FFD400] text-[#0F3D3E] font-semibold inline-flex items-center gap-1"
            >
              <Copy className="w-3.5 h-3.5" /> Copy
            </button>
          </div>
        </div>
      )}

      <div className="grid lg:grid-cols-2 gap-6 mb-6">
        {/* Departments */}
        <div className="bg-white rounded-lg border border-[#D5CDBD] p-5">
          <h2 className="text-sm font-semibold text-[#0F3D3E] mb-3">Departments</h2>
          <form onSubmit={handleAddDept} className="flex gap-2 mb-4">
            <input
              required
              placeholder="New department name..."
              value={deptName}
              onChange={(e) => setDeptName(e.target.value)}
              className="flex-1 px-3 py-2 text-sm rounded border border-[#D5CDBD]"
            />
            <button
              type="submit"
              className="px-3.5 py-2 rounded bg-[#FFD400] text-[#0F3D3E] text-sm font-semibold"
            >
              <Plus className="w-4 h-4" />
            </button>
          </form>
          <ul className="divide-y divide-[#EAE5DC] text-sm">
            {departments.map((d) => (
              <li key={d.id} className="py-2">
                {d.name}
              </li>
            ))}
          </ul>
        </div>

        {/* Locations */}
        <div className="bg-white rounded-lg border border-[#D5CDBD] p-5">
          <h2 className="text-sm font-semibold text-[#0F3D3E] mb-3">Locations / Branches</h2>
          <form onSubmit={handleAddLocation} className="flex gap-2 mb-4">
            <input
              required
              placeholder="New location name..."
              value={locName}
              onChange={(e) => setLocName(e.target.value)}
              className="flex-1 px-3 py-2 text-sm rounded border border-[#D5CDBD]"
            />
            <button
              type="submit"
              className="px-3.5 py-2 rounded bg-[#FFD400] text-[#0F3D3E] text-sm font-semibold"
            >
              <Plus className="w-4 h-4" />
            </button>
          </form>
          <ul className="divide-y divide-[#EAE5DC] text-sm">
            {locations.map((l) => (
              <li key={l.id} className="py-2">
                {l.name}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Attendance Terminals */}
      <div className="bg-white rounded-lg border border-[#D5CDBD] p-5 mb-6">
        <h2 className="text-sm font-semibold text-[#0F3D3E] mb-3 flex items-center gap-2">
          <MonitorSmartphone className="w-4 h-4" /> Attendance Terminals
        </h2>
        <form onSubmit={handleAddTerminal} className="grid sm:grid-cols-4 gap-3 mb-4">
          <input
            required
            placeholder="Terminal Name (e.g. Lobby Tablet)"
            value={termName}
            onChange={(e) => setTermName(e.target.value)}
            className="px-3 py-2 text-sm rounded border border-[#D5CDBD]"
          />
          <input
            required
            placeholder="Device ID (e.g. LOBBY-01)"
            value={termDevice}
            onChange={(e) => setTermDevice(e.target.value)}
            className="px-3 py-2 text-sm rounded border border-[#D5CDBD]"
          />
          <select
            value={termLocation}
            onChange={(e) => setTermLocation(e.target.value)}
            className="px-3 py-2 text-sm rounded border border-[#D5CDBD]"
          >
            <option value="">Default Location</option>
            {locations.map((l) => (
              <option key={l.id} value={l.id}>
                {l.name}
              </option>
            ))}
          </select>
          <button
            type="submit"
            className="px-4 py-2 rounded bg-[#0F3D3E] text-white text-sm font-semibold"
          >
            Register Terminal
          </button>
        </form>

        <table className="w-full text-sm">
          <thead className="bg-[#F4F1EA] text-xs uppercase text-[#0F3D3E]">
            <tr>
              <th className="text-left px-4 py-2">Name</th>
              <th className="text-left px-4 py-2">Device ID</th>
              <th className="text-left px-4 py-2">Location</th>
              <th className="text-left px-4 py-2">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#EAE5DC]">
            {terminals.map((t) => (
              <tr key={t.id}>
                <td className="px-4 py-2 font-medium">{t.name}</td>
                <td className="px-4 py-2 font-mono text-xs">{t.device_identifier}</td>
                <td className="px-4 py-2">{t.location_name || "Default"}</td>
                <td className="px-4 py-2">
                  <StatusBadge status={t.is_active ? "active" : "inactive"} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Attendance Policies */}
      {settings && (
        <form
          onSubmit={handleSaveSettings}
          className="bg-white rounded-lg border border-[#D5CDBD] p-5 space-y-4"
        >
          <h2 className="text-sm font-semibold text-[#0F3D3E]">
            Organization Attendance Policies
          </h2>
          <div className="grid sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs text-[#546A6B] mb-1">
                Default Grace Period (min)
              </label>
              <input
                type="number"
                value={settings.default_grace_period_minutes}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    default_grace_period_minutes: Number(e.target.value),
                  })
                }
                className="w-full px-3 py-2 text-sm rounded border border-[#D5CDBD]"
              />
            </div>
            <div>
              <label className="block text-xs text-[#546A6B] mb-1">
                Expected Work Minutes / Day
              </label>
              <input
                type="number"
                value={settings.default_expected_work_minutes}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    default_expected_work_minutes: Number(e.target.value),
                  })
                }
                className="w-full px-3 py-2 text-sm rounded border border-[#D5CDBD]"
              />
            </div>
            <div>
              <label className="block text-xs text-[#546A6B] mb-1">
                Terminal Auto-Reset (sec)
              </label>
              <input
                type="number"
                value={settings.terminal_reset_delay_seconds}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    terminal_reset_delay_seconds: Number(e.target.value),
                  })
                }
                className="w-full px-3 py-2 text-sm rounded border border-[#D5CDBD]"
              />
            </div>
          </div>
          <div className="flex flex-wrap gap-6 text-xs text-[#0F3D3E]">
            <label className="inline-flex items-center gap-2">
              <input
                type="checkbox"
                checked={settings.break_tracking_enabled}
                onChange={(e) =>
                  setSettings({ ...settings, break_tracking_enabled: e.target.checked })
                }
              />
              Enable Break Tracking
            </label>
            <label className="inline-flex items-center gap-2">
              <input
                type="checkbox"
                checked={settings.overtime_enabled}
                onChange={(e) =>
                  setSettings({ ...settings, overtime_enabled: e.target.checked })
                }
              />
              Enable Overtime Calculation
            </label>
            <label className="inline-flex items-center gap-2">
              <input
                type="checkbox"
                checked={settings.overtime_requires_approval}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    overtime_requires_approval: e.target.checked,
                  })
                }
              />
              Overtime Requires Approval
            </label>
          </div>
          <button
            type="submit"
            className="px-4 py-2 rounded bg-[#FFD400] text-[#0F3D3E] text-sm font-semibold hover:bg-[#E6BF00]"
          >
            Save Policies
          </button>
        </form>
      )}
    </AppShell>
  );
}
