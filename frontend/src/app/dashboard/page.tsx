"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Coffee,
  LogIn,
  LogOut,
  Users,
} from "lucide-react";
import { AppShell } from "@/components/ui/AppShell";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ApiError, apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

interface DashboardMetrics {
  total_active_employees: number;
  present_today: number;
  absent_today: number;
  late_today: number;
  currently_working: number;
  currently_on_break: number;
  incomplete_attendance: number;
  approved_leave_today: number;
  daily_trend: { date: string; present: number; late: number; absent: number }[];
  department_comparison: {
    department: string;
    total: number;
    present: number;
    late: number;
  }[];
}

interface AttendanceSession {
  id: string;
  employee_code: string;
  employee_name: string;
  department_name: string | null;
  shift_name: string | null;
  work_date: string;
  check_in_at: string;
  check_out_at: string | null;
  status: string;
  is_open: boolean;
  net_minutes: number;
}

interface MyStatus {
  state: "checked_out" | "working" | "on_break";
  check_in_at: string | null;
  break_started_at: string | null;
}

export default function DashboardPage() {
  const { user, hasPermission } = useAuth();
  const isManagerView =
    hasPermission("attendance:view_all") ||
    hasPermission("attendance:view_department");

  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [sessions, setSessions] = useState<AttendanceSession[]>([]);
  const [myStatus, setMyStatus] = useState<MyStatus | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    if (!user) return;
    try {
      if (isManagerView) {
        const [m, s] = await Promise.all([
          apiFetch<DashboardMetrics>("/attendance/dashboard"),
          apiFetch<AttendanceSession[]>("/attendance/sessions?limit=25"),
        ]);
        setMetrics(m);
        setSessions(s);
      } else {
        const [st, s] = await Promise.all([
          apiFetch<MyStatus>("/attendance/my/status"),
          apiFetch<AttendanceSession[]>("/attendance/sessions?limit=15"),
        ]);
        setMyStatus(st);
        setSessions(s);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load dashboard");
    }
  }, [user, isManagerView]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleEmployeeAction = async (
    endpoint:
      | "/attendance/my/check-in"
      | "/attendance/my/check-out"
      | "/attendance/my/break/start"
      | "/attendance/my/break/end"
  ) => {
    setError(null);
    setActionMessage(null);
    try {
      await apiFetch(endpoint, { method: "POST" });
      setActionMessage("Attendance action recorded.");
      await loadData();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Action failed");
    }
  };

  if (!isManagerView) {
    return (
      <AppShell
        title="My Attendance"
        subtitle="Record your daily attendance and view your recent sessions"
      >
        {error && (
          <div className="mb-4 p-3 rounded bg-red-50 border border-red-200 text-xs text-red-800">
            {error}
          </div>
        )}
        {actionMessage && (
          <div className="mb-4 p-3 rounded bg-emerald-50 border border-emerald-200 text-xs text-emerald-900">
            {actionMessage}
          </div>
        )}

        <div className="bg-white rounded-lg border border-[#D5CDBD] p-6 mb-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <div className="text-xs font-medium text-[#546A6B] uppercase tracking-wider">
                Current Status
              </div>
              <div className="mt-2">
                <StatusBadge status={myStatus?.state || "checked_out"} />
              </div>
              {myStatus?.check_in_at && (
                <div className="text-xs text-[#546A6B] mt-2">
                  Checked in at {new Date(myStatus.check_in_at).toLocaleTimeString()}
                </div>
              )}
            </div>

            <div className="flex flex-wrap gap-3">
              {myStatus?.state === "checked_out" && (
                <button
                  onClick={() => handleEmployeeAction("/attendance/my/check-in")}
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-md bg-[#FFD400] text-[#0F3D3E] font-semibold text-sm hover:bg-[#E6BF00]"
                >
                  <LogIn className="w-4 h-4" /> Check In
                </button>
              )}
              {myStatus?.state === "working" && (
                <>
                  <button
                    onClick={() => handleEmployeeAction("/attendance/my/break/start")}
                    className="inline-flex items-center gap-2 px-4 py-2.5 rounded-md bg-[#F4F1EA] text-[#0F3D3E] border border-[#C9C0B1] font-medium text-sm hover:bg-[#E6E0D4]"
                  >
                    <Coffee className="w-4 h-4" /> Start Break
                  </button>
                  <button
                    onClick={() => handleEmployeeAction("/attendance/my/check-out")}
                    className="inline-flex items-center gap-2 px-5 py-2.5 rounded-md bg-[#0F3D3E] text-white font-semibold text-sm hover:bg-[#165254]"
                  >
                    <LogOut className="w-4 h-4 text-[#FFD400]" /> Check Out
                  </button>
                </>
              )}
              {myStatus?.state === "on_break" && (
                <button
                  onClick={() => handleEmployeeAction("/attendance/my/break/end")}
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-md bg-[#FFD400] text-[#0F3D3E] font-semibold text-sm hover:bg-[#E6BF00]"
                >
                  <Coffee className="w-4 h-4" /> End Break
                </button>
              )}
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg border border-[#D5CDBD] overflow-hidden">
          <div className="px-6 py-4 border-b border-[#D5CDBD]">
            <h2 className="text-sm font-semibold text-[#0F3D3E]">Recent Attendance History</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-[#F4F1EA] text-[#0F3D3E] text-xs uppercase">
                <tr>
                  <th className="text-left px-6 py-3">Date</th>
                  <th className="text-left px-6 py-3">Shift</th>
                  <th className="text-left px-6 py-3">Check In</th>
                  <th className="text-left px-6 py-3">Check Out</th>
                  <th className="text-left px-6 py-3">Net Hours</th>
                  <th className="text-left px-6 py-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#EAE5DC]">
                {sessions.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-6 py-8 text-center text-xs text-[#546A6B]">
                      No attendance records found.
                    </td>
                  </tr>
                ) : (
                  sessions.map((s) => (
                    <tr key={s.id}>
                      <td className="px-6 py-3 font-medium">{s.work_date}</td>
                      <td className="px-6 py-3 text-[#546A6B]">{s.shift_name || "Default"}</td>
                      <td className="px-6 py-3">{new Date(s.check_in_at).toLocaleTimeString()}</td>
                      <td className="px-6 py-3">
                        {s.check_out_at ? new Date(s.check_out_at).toLocaleTimeString() : "—"}
                      </td>
                      <td className="px-6 py-3">{(s.net_minutes / 60).toFixed(2)}h</td>
                      <td className="px-6 py-3">
                        <StatusBadge status={s.status} />
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </AppShell>
    );
  }

  const statCards = [
    { label: "Active Employees", value: metrics?.total_active_employees ?? 0, Icon: Users, accent: false },
    { label: "Present Today", value: metrics?.present_today ?? 0, Icon: CheckCircle2, accent: true },
    { label: "Currently Working", value: metrics?.currently_working ?? 0, Icon: Clock, accent: false },
    { label: "Late Today", value: metrics?.late_today ?? 0, Icon: AlertTriangle, accent: false },
    { label: "Absent Today", value: metrics?.absent_today ?? 0, Icon: AlertTriangle, accent: false },
    { label: "On Break", value: metrics?.currently_on_break ?? 0, Icon: Coffee, accent: false },
    { label: "Incomplete", value: metrics?.incomplete_attendance ?? 0, Icon: AlertTriangle, accent: false },
    { label: "Approved Leave", value: metrics?.approved_leave_today ?? 0, Icon: Users, accent: false },
  ];

  return (
    <AppShell
      title="Workforce Attendance Overview"
      subtitle="Real-time attendance status, trends, and department metrics"
    >
      {error && (
        <div className="mb-4 p-3 rounded bg-red-50 border border-red-200 text-xs text-red-800">
          {error}
        </div>
      )}

      {/* 8 KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {statCards.map((card) => {
          const Icon = card.Icon;
          return (
            <div
              key={card.label}
              className={`rounded-lg border p-4 ${
                card.accent
                  ? "bg-[#0F3D3E] text-white border-[#0F3D3E]"
                  : "bg-white text-[#0F3D3E] border-[#D5CDBD]"
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span
                  className={`text-xs font-medium ${
                    card.accent ? "text-[#D7E4E4]" : "text-[#546A6B]"
                  }`}
                >
                  {card.label}
                </span>
                <Icon
                  className={`w-4 h-4 ${
                    card.accent ? "text-[#FFD400]" : "text-[#0F3D3E]"
                  }`}
                />
              </div>
              <div className="text-2xl font-bold tabular-nums">{card.value}</div>
            </div>
          );
        })}
      </div>

      {/* Charts */}
      <div className="grid lg:grid-cols-2 gap-6 mb-6">
        <div className="bg-white rounded-lg border border-[#D5CDBD] p-5">
          <h2 className="text-sm font-semibold text-[#0F3D3E] mb-4">
            7-Day Attendance Trend
          </h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={metrics?.daily_trend || []}>
                <CartesianGrid strokeDasharray="3 3" stroke="#EAE5DC" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip />
                <Legend />
                <Bar dataKey="present" name="Present" fill="#0F3D3E" radius={[3, 3, 0, 0]} />
                <Bar dataKey="late" name="Late" fill="#FFD400" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-white rounded-lg border border-[#D5CDBD] p-5">
          <h2 className="text-sm font-semibold text-[#0F3D3E] mb-4">
            Department Attendance Today
          </h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={metrics?.department_comparison || []}>
                <CartesianGrid strokeDasharray="3 3" stroke="#EAE5DC" />
                <XAxis dataKey="department" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip />
                <Legend />
                <Bar dataKey="total" name="Total Staff" fill="#C9C0B1" radius={[3, 3, 0, 0]} />
                <Bar dataKey="present" name="Present" fill="#0F3D3E" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Live Attendance Table */}
      <div className="bg-white rounded-lg border border-[#D5CDBD] overflow-hidden">
        <div className="px-6 py-4 border-b border-[#D5CDBD] flex items-center justify-between">
          <h2 className="text-sm font-semibold text-[#0F3D3E]">
            Live Attendance Overview
          </h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[#F4F1EA] text-[#0F3D3E] text-xs uppercase">
              <tr>
                <th className="text-left px-6 py-3">Employee</th>
                <th className="text-left px-6 py-3">ID</th>
                <th className="text-left px-6 py-3">Department</th>
                <th className="text-left px-6 py-3">Shift</th>
                <th className="text-left px-6 py-3">Check In</th>
                <th className="text-left px-6 py-3">Check Out</th>
                <th className="text-left px-6 py-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#EAE5DC]">
              {sessions.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-8 text-center text-xs text-[#546A6B]">
                    No attendance sessions recorded yet.
                  </td>
                </tr>
              ) : (
                sessions.map((s) => (
                  <tr key={s.id} className="hover:bg-[#FAF9F6]">
                    <td className="px-6 py-3 font-medium text-[#0F3D3E]">
                      {s.employee_name}
                    </td>
                    <td className="px-6 py-3 font-mono text-xs">{s.employee_code}</td>
                    <td className="px-6 py-3 text-[#546A6B]">
                      {s.department_name || "Unassigned"}
                    </td>
                    <td className="px-6 py-3 text-[#546A6B]">
                      {s.shift_name || "Unassigned"}
                    </td>
                    <td className="px-6 py-3">
                      {new Date(s.check_in_at).toLocaleTimeString()}
                    </td>
                    <td className="px-6 py-3">
                      {s.check_out_at
                        ? new Date(s.check_out_at).toLocaleTimeString()
                        : "Active"}
                    </td>
                    <td className="px-6 py-3">
                      <StatusBadge status={s.status} />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </AppShell>
  );
}
