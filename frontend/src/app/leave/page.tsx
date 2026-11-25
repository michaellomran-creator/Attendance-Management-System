"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Check, X } from "lucide-react";
import { AppShell } from "@/components/ui/AppShell";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ApiError, apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

interface LeaveType {
  id: string;
  name: string;
}

interface LeaveRequest {
  id: string;
  employee_name: string;
  employee_code: string;
  department_name: string | null;
  leave_type_name: string;
  start_date: string;
  end_date: string;
  reason: string;
  status: string;
  reviewer_comment: string | null;
}

export default function LeavePage() {
  const { hasPermission } = useAuth();
  const canRequest = hasPermission("leave:request");
  const canApprove = hasPermission("leave:approve");

  const [types, setTypes] = useState<LeaveType[]>([]);
  const [requests, setRequests] = useState<LeaveRequest[]>([]);
  const [form, setForm] = useState({
    leave_type_id: "",
    start_date: "",
    end_date: "",
    reason: "",
  });
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [t, r] = await Promise.all([
        apiFetch<LeaveType[]>("/leave/types"),
        apiFetch<LeaveRequest[]>("/leave/requests"),
      ]);
      setTypes(t);
      setRequests(r);
      if (t.length > 0 && !form.leave_type_id) {
        setForm((prev) => ({ ...prev, leave_type_id: t[0].id }));
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load leave requests");
    }
  }, [form.leave_type_id]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await apiFetch("/leave/requests", {
        method: "POST",
        body: JSON.stringify(form),
      });
      setForm({ ...form, start_date: "", end_date: "", reason: "" });
      await loadData();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to submit request");
    }
  };

  const handleReview = async (id: string, status: "approved" | "rejected") => {
    setError(null);
    try {
      await apiFetch(`/leave/requests/${id}/review`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      await loadData();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Review failed");
    }
  };

  return (
    <AppShell title="Leave Management" subtitle="Submit and review employee leave requests">
      {error && (
        <div className="mb-4 p-3 rounded bg-red-50 border border-red-200 text-xs text-red-800">
          {error}
        </div>
      )}

      {canRequest && (
        <form
          onSubmit={handleSubmit}
          className="bg-white rounded-lg border border-[#D5CDBD] p-5 mb-6 space-y-3"
        >
          <h2 className="text-sm font-semibold text-[#0F3D3E]">Request Leave</h2>
          <div className="grid sm:grid-cols-3 gap-3">
            <select
              required
              value={form.leave_type_id}
              onChange={(e) => setForm({ ...form, leave_type_id: e.target.value })}
              className="px-3 py-2 text-sm rounded border border-[#D5CDBD]"
            >
              {types.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
            <input
              type="date"
              required
              value={form.start_date}
              onChange={(e) => setForm({ ...form, start_date: e.target.value })}
              className="px-3 py-2 text-sm rounded border border-[#D5CDBD]"
            />
            <input
              type="date"
              required
              value={form.end_date}
              onChange={(e) => setForm({ ...form, end_date: e.target.value })}
              className="px-3 py-2 text-sm rounded border border-[#D5CDBD]"
            />
          </div>
          <textarea
            required
            rows={2}
            placeholder="Reason for leave..."
            value={form.reason}
            onChange={(e) => setForm({ ...form, reason: e.target.value })}
            className="w-full px-3 py-2 text-sm rounded border border-[#D5CDBD]"
          />
          <button
            type="submit"
            className="px-4 py-2 rounded bg-[#FFD400] text-[#0F3D3E] text-sm font-semibold hover:bg-[#E6BF00]"
          >
            Submit Leave Request
          </button>
        </form>
      )}

      <div className="bg-white rounded-lg border border-[#D5CDBD] overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[#F4F1EA] text-xs uppercase text-[#0F3D3E]">
            <tr>
              <th className="text-left px-5 py-3">Employee</th>
              <th className="text-left px-5 py-3">Type</th>
              <th className="text-left px-5 py-3">Dates</th>
              <th className="text-left px-5 py-3">Reason</th>
              <th className="text-left px-5 py-3">Status</th>
              {canApprove && <th className="text-right px-5 py-3">Actions</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-[#EAE5DC]">
            {requests.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-5 py-8 text-center text-xs text-[#546A6B]">
                  No leave requests found.
                </td>
              </tr>
            ) : (
              requests.map((r) => (
                <tr key={r.id}>
                  <td className="px-5 py-3">
                    <div className="font-medium">{r.employee_name}</div>
                    <div className="text-xs text-[#546A6B]">{r.employee_code}</div>
                  </td>
                  <td className="px-5 py-3">{r.leave_type_name}</td>
                  <td className="px-5 py-3">
                    {r.start_date} to {r.end_date}
                  </td>
                  <td className="px-5 py-3 text-xs text-[#546A6B] max-w-xs">{r.reason}</td>
                  <td className="px-5 py-3">
                    <StatusBadge status={r.status} />
                  </td>
                  {canApprove && (
                    <td className="px-5 py-3 text-right">
                      {r.status === "pending" && (
                        <div className="inline-flex gap-2">
                          <button
                            onClick={() => handleReview(r.id, "approved")}
                            className="p-1.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-200 hover:bg-emerald-100"
                            title="Approve"
                          >
                            <Check className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleReview(r.id, "rejected")}
                            className="p-1.5 rounded bg-red-50 text-red-800 border border-red-200 hover:bg-red-100"
                            title="Reject"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </div>
                      )}
                    </td>
                  )}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </AppShell>
  );
}
