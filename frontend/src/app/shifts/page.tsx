"use client";

import React, { useCallback, useEffect, useState } from "react";
import { CalendarClock, Plus } from "lucide-react";
import { AppShell } from "@/components/ui/AppShell";
import { ApiError, apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

interface Shift {
  id: string;
  name: string;
  shift_type: string;
  start_time: string;
  end_time: string;
  crosses_midnight: boolean;
  grace_period_minutes: number;
  expected_work_minutes: number;
}

interface ShiftAssignment {
  id: string;
  shift_name: string | null;
  employee_name: string | null;
  department_name: string | null;
  effective_from: string;
  effective_to: string | null;
}

interface Employee {
  id: string;
  employee_code: string;
  first_name: string;
  last_name: string;
}

interface Department {
  id: string;
  name: string;
}

export default function ShiftsPage() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("shift:manage");

  const [shifts, setShifts] = useState<Shift[]>([]);
  const [assignments, setAssignments] = useState<ShiftAssignment[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [shiftForm, setShiftForm] = useState({
    name: "",
    shift_type: "morning",
    start_time: "08:00",
    end_time: "17:00",
    crosses_midnight: false,
    grace_period_minutes: 10,
    expected_work_minutes: 480,
  });

  const [assignForm, setAssignForm] = useState({
    shift_id: "",
    employee_id: "",
    department_id: "",
    effective_from: "",
  });

  useEffect(() => {
    setAssignForm((prev) => ({
      ...prev,
      effective_from: prev.effective_from || new Date().toISOString().slice(0, 10),
    }));
  }, []);

  const loadData = useCallback(async () => {
    try {
      const [s, a] = await Promise.all([
        apiFetch<Shift[]>("/shifts"),
        apiFetch<ShiftAssignment[]>("/shifts/assignments"),
      ]);
      setShifts(s);
      setAssignments(a);
      if (canManage) {
        const [empData, deptData] = await Promise.all([
          apiFetch<{ items: Employee[] }>("/employees?page_size=200"),
          apiFetch<Department[]>("/organizations/departments"),
        ]);
        setEmployees(empData.items);
        setDepartments(deptData);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load shifts");
    }
  }, [canManage]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleCreateShift = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await apiFetch("/shifts", {
        method: "POST",
        body: JSON.stringify({
          ...shiftForm,
          start_time: `${shiftForm.start_time}:00`,
          end_time: `${shiftForm.end_time}:00`,
        }),
      });
      setShiftForm({ ...shiftForm, name: "" });
      await loadData();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create shift");
    }
  };

  const handleAssignShift = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await apiFetch("/shifts/assignments", {
        method: "POST",
        body: JSON.stringify({
          shift_id: assignForm.shift_id,
          employee_id: assignForm.employee_id || null,
          department_id: assignForm.department_id || null,
          effective_from: assignForm.effective_from,
        }),
      });
      await loadData();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to assign shift");
    }
  };

  return (
    <AppShell
      title="Shifts & Schedules"
      subtitle="Configure standard and overnight shifts, grace periods, and assignments"
    >
      {error && (
        <div className="mb-4 p-3 rounded bg-red-50 border border-red-200 text-xs text-red-800">
          {error}
        </div>
      )}

      {canManage && (
        <div className="grid lg:grid-cols-2 gap-6 mb-6">
          {/* Create Shift */}
          <form
            onSubmit={handleCreateShift}
            className="bg-white rounded-lg border border-[#D5CDBD] p-5 space-y-3"
          >
            <h2 className="text-sm font-semibold text-[#0F3D3E] flex items-center gap-2">
              <CalendarClock className="w-4 h-4" /> Create Shift
            </h2>
            <div className="grid grid-cols-2 gap-3">
              <input
                required
                placeholder="Shift Name (e.g. Night Shift)"
                value={shiftForm.name}
                onChange={(e) => setShiftForm({ ...shiftForm, name: e.target.value })}
                className="px-3 py-2 text-sm rounded border border-[#D5CDBD]"
              />
              <select
                value={shiftForm.shift_type}
                onChange={(e) => setShiftForm({ ...shiftForm, shift_type: e.target.value })}
                className="px-3 py-2 text-sm rounded border border-[#D5CDBD]"
              >
                <option value="morning">Morning</option>
                <option value="afternoon">Afternoon</option>
                <option value="night">Night (Overnight)</option>
                <option value="general">General Office</option>
                <option value="rotating">Rotating</option>
                <option value="custom">Custom</option>
              </select>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-[11px] text-[#546A6B] mb-1">Start</label>
                <input
                  type="time"
                  required
                  value={shiftForm.start_time}
                  onChange={(e) => setShiftForm({ ...shiftForm, start_time: e.target.value })}
                  className="w-full px-3 py-2 text-sm rounded border border-[#D5CDBD]"
                />
              </div>
              <div>
                <label className="block text-[11px] text-[#546A6B] mb-1">End</label>
                <input
                  type="time"
                  required
                  value={shiftForm.end_time}
                  onChange={(e) => setShiftForm({ ...shiftForm, end_time: e.target.value })}
                  className="w-full px-3 py-2 text-sm rounded border border-[#D5CDBD]"
                />
              </div>
              <div>
                <label className="block text-[11px] text-[#546A6B] mb-1">Grace (min)</label>
                <input
                  type="number"
                  min={0}
                  value={shiftForm.grace_period_minutes}
                  onChange={(e) =>
                    setShiftForm({ ...shiftForm, grace_period_minutes: Number(e.target.value) })
                  }
                  className="w-full px-3 py-2 text-sm rounded border border-[#D5CDBD]"
                />
              </div>
            </div>
            <label className="inline-flex items-center gap-2 text-xs text-[#0F3D3E]">
              <input
                type="checkbox"
                checked={shiftForm.crosses_midnight}
                onChange={(e) =>
                  setShiftForm({ ...shiftForm, crosses_midnight: e.target.checked })
                }
              />
              Overnight shift (crosses midnight)
            </label>
            <div>
              <button
                type="submit"
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded bg-[#FFD400] text-[#0F3D3E] text-sm font-semibold hover:bg-[#E6BF00]"
              >
                <Plus className="w-4 h-4" /> Save Shift
              </button>
            </div>
          </form>

          {/* Assign Shift */}
          <form
            onSubmit={handleAssignShift}
            className="bg-white rounded-lg border border-[#D5CDBD] p-5 space-y-3"
          >
            <h2 className="text-sm font-semibold text-[#0F3D3E]">Assign Shift</h2>
            <select
              required
              value={assignForm.shift_id}
              onChange={(e) => setAssignForm({ ...assignForm, shift_id: e.target.value })}
              className="w-full px-3 py-2 text-sm rounded border border-[#D5CDBD]"
            >
              <option value="">Select Shift...</option>
              {shifts.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.start_time.slice(0, 5)} - {s.end_time.slice(0, 5)})
                </option>
              ))}
            </select>

            <div className="grid grid-cols-2 gap-3">
              <select
                value={assignForm.employee_id}
                onChange={(e) =>
                  setAssignForm({ ...assignForm, employee_id: e.target.value, department_id: "" })
                }
                className="px-3 py-2 text-sm rounded border border-[#D5CDBD]"
              >
                <option value="">Individual Employee...</option>
                {employees.map((emp) => (
                  <option key={emp.id} value={emp.id}>
                    {emp.employee_code} - {emp.first_name} {emp.last_name}
                  </option>
                ))}
              </select>

              <select
                value={assignForm.department_id}
                onChange={(e) =>
                  setAssignForm({ ...assignForm, department_id: e.target.value, employee_id: "" })
                }
                className="px-3 py-2 text-sm rounded border border-[#D5CDBD]"
              >
                <option value="">Or Department...</option>
                {departments.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex items-center gap-3">
              <input
                type="date"
                required
                value={assignForm.effective_from}
                onChange={(e) =>
                  setAssignForm({ ...assignForm, effective_from: e.target.value })
                }
                className="px-3 py-2 text-sm rounded border border-[#D5CDBD]"
              />
              <button
                type="submit"
                className="px-4 py-2 rounded bg-[#0F3D3E] text-white text-sm font-semibold hover:bg-[#165254]"
              >
                Assign
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Shifts Table */}
      <div className="bg-white rounded-lg border border-[#D5CDBD] overflow-hidden mb-6">
        <div className="px-5 py-3 border-b border-[#D5CDBD] font-semibold text-sm text-[#0F3D3E]">
          Configured Shifts
        </div>
        <table className="w-full text-sm">
          <thead className="bg-[#F4F1EA] text-xs uppercase text-[#0F3D3E]">
            <tr>
              <th className="text-left px-5 py-3">Name</th>
              <th className="text-left px-5 py-3">Type</th>
              <th className="text-left px-5 py-3">Window</th>
              <th className="text-left px-5 py-3">Overnight</th>
              <th className="text-left px-5 py-3">Grace Period</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#EAE5DC]">
            {shifts.map((s) => (
              <tr key={s.id}>
                <td className="px-5 py-3 font-medium">{s.name}</td>
                <td className="px-5 py-3 capitalize">{s.shift_type}</td>
                <td className="px-5 py-3">
                  {s.start_time.slice(0, 5)} – {s.end_time.slice(0, 5)}
                </td>
                <td className="px-5 py-3">{s.crosses_midnight ? "Yes (Next Day)" : "No"}</td>
                <td className="px-5 py-3">{s.grace_period_minutes} min</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Assignments Table */}
      <div className="bg-white rounded-lg border border-[#D5CDBD] overflow-hidden">
        <div className="px-5 py-3 border-b border-[#D5CDBD] font-semibold text-sm text-[#0F3D3E]">
          Shift Assignments
        </div>
        <table className="w-full text-sm">
          <thead className="bg-[#F4F1EA] text-xs uppercase text-[#0F3D3E]">
            <tr>
              <th className="text-left px-5 py-3">Shift</th>
              <th className="text-left px-5 py-3">Target</th>
              <th className="text-left px-5 py-3">Effective From</th>
              <th className="text-left px-5 py-3">Effective To</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#EAE5DC]">
            {assignments.map((a) => (
              <tr key={a.id}>
                <td className="px-5 py-3 font-medium">{a.shift_name}</td>
                <td className="px-5 py-3">
                  {a.employee_name || (a.department_name ? `Dept: ${a.department_name}` : "—")}
                </td>
                <td className="px-5 py-3">{a.effective_from}</td>
                <td className="px-5 py-3">{a.effective_to || "Ongoing"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </AppShell>
  );
}
