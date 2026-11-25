"use client";

import React, { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/ui/AppShell";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ApiError, apiFetch } from "@/lib/api";

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
  gross_minutes: number;
  break_minutes: number;
  net_minutes: number;
  overtime_minutes: number;
  late_minutes: number;
}

export default function AttendanceRecordsPage() {
  const [sessions, setSessions] = useState<AttendanceSession[]>([]);
  const [workDate, setWorkDate] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [error, setError] = useState<string | null>(null);

  const loadSessions = useCallback(async () => {
    try {
      const params = new URLSearchParams({ limit: "150" });
      if (workDate) params.set("work_date", workDate);
      if (statusFilter) params.set("status", statusFilter);
      const data = await apiFetch<AttendanceSession[]>(
        `/attendance/sessions?${params.toString()}`
      );
      setSessions(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load records");
    }
  }, [workDate, statusFilter]);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  return (
    <AppShell
      title="Attendance Records"
      subtitle="Historical and active attendance sessions with gross, break, net, and overtime hours"
    >
      {error && (
        <div className="mb-4 p-3 rounded bg-red-50 border border-red-200 text-xs text-red-800">
          {error}
        </div>
      )}

      <div className="bg-white rounded-lg border border-[#D5CDBD] p-4 mb-6 flex flex-wrap gap-3 items-center">
        <div>
          <label className="block text-[11px] text-[#546A6B] mb-1">Work Date</label>
          <input
            type="date"
            value={workDate}
            onChange={(e) => setWorkDate(e.target.value)}
            className="px-3 py-2 text-sm rounded border border-[#D5CDBD]"
          />
        </div>
        <div>
          <label className="block text-[11px] text-[#546A6B] mb-1">Status</label>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2 text-sm rounded border border-[#D5CDBD]"
          >
            <option value="">All Statuses</option>
            <option value="on_time">On Time</option>
            <option value="present">Present</option>
            <option value="late">Late</option>
            <option value="early_departure">Early Departure</option>
            <option value="overtime">Overtime</option>
          </select>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-[#D5CDBD] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[#F4F1EA] text-xs uppercase text-[#0F3D3E]">
              <tr>
                <th className="text-left px-4 py-3">Date</th>
                <th className="text-left px-4 py-3">Employee</th>
                <th className="text-left px-4 py-3">Department</th>
                <th className="text-left px-4 py-3">Check In</th>
                <th className="text-left px-4 py-3">Check Out</th>
                <th className="text-left px-4 py-3">Net / Break</th>
                <th className="text-left px-4 py-3">Overtime</th>
                <th className="text-left px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#EAE5DC]">
              {sessions.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-xs text-[#546A6B]">
                    No attendance records match your filters.
                  </td>
                </tr>
              ) : (
                sessions.map((s) => (
                  <tr key={s.id} className="hover:bg-[#FAF9F6]">
                    <td className="px-4 py-3 font-medium">{s.work_date}</td>
                    <td className="px-4 py-3">
                      <div className="font-medium text-[#0F3D3E]">{s.employee_name}</div>
                      <div className="text-xs text-[#546A6B]">{s.employee_code}</div>
                    </td>
                    <td className="px-4 py-3 text-[#546A6B]">
                      {s.department_name || "Unassigned"}
                    </td>
                    <td className="px-4 py-3">{new Date(s.check_in_at).toLocaleTimeString()}</td>
                    <td className="px-4 py-3">
                      {s.check_out_at ? new Date(s.check_out_at).toLocaleTimeString() : "Active"}
                    </td>
                    <td className="px-4 py-3 text-xs">
                      {(s.net_minutes / 60).toFixed(2)}h net ({s.break_minutes}m break)
                    </td>
                    <td className="px-4 py-3 text-xs">{s.overtime_minutes}m</td>
                    <td className="px-4 py-3">
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
