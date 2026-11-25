"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Check, X } from "lucide-react";
import { AppShell } from "@/components/ui/AppShell";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ApiError, apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

interface CorrectionRequest {
  id: string;
  employee_name: string;
  employee_code: string;
  target_date: string;
  correction_type: string;
  requested_check_in_at: string | null;
  requested_check_out_at: string | null;
  reason: string;
  status: string;
  reviewer_comment: string | null;
}

export default function CorrectionsPage() {
  const { hasPermission } = useAuth();
  const canRequest = hasPermission("attendance:correct_request");
  const canApprove = hasPermission("attendance:correct_approve");

  const [requests, setRequests] = useState<CorrectionRequest[]>([]);
  const [form, setForm] = useState({
    target_date: "",
    correction_type: "missed_check_out",
    requested_check_in_at: "",
    requested_check_out_at: "",
    reason: "",
  });
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setForm((prev) => ({
      ...prev,
      target_date: prev.target_date || new Date().toISOString().slice(0, 10),
    }));
  }, []);

  const loadData = useCallback(async () => {
    try {
      const data = await apiFetch<CorrectionRequest[]>("/corrections");
      setRequests(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load corrections");
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await apiFetch("/corrections", {
        method: "POST",
        body: JSON.stringify({
          target_date: form.target_date,
          correction_type: form.correction_type,
          requested_check_in_at: form.requested_check_in_at
            ? new Date(form.requested_check_in_at).toISOString()
            : null,
          requested_check_out_at: form.requested_check_out_at
            ? new Date(form.requested_check_out_at).toISOString()
            : null,
          reason: form.reason,
        }),
      });
      setForm({ ...form, reason: "", requested_check_in_at: "", requested_check_out_at: "" });
      await loadData();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to submit correction");
    }
  };

  const handleReview = async (id: string, status: "approved" | "rejected") => {
    setError(null);
    try {
      await apiFetch(`/corrections/${id}/review`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      await loadData();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Review failed");
    }
  };

  return (
    <AppShell
      title="Attendance Corrections"
      subtitle="Auditable workflow for missed check-ins, missed check-outs, and time adjustments"
    >
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
          <h2 className="text-sm font-semibold text-[#0F3D3E]">
            Submit Attendance Correction
          </h2>
          <div className="grid sm:grid-cols-4 gap-3">
            <div>
              <label className="block text-[11px] text-[#546A6B] mb-1">Date</label>
              <input
                type="date"
                required
                value={form.target_date}
                onChange={(e) => setForm({ ...form, target_date: e.target.value })}
                className="w-full px-3 py-2 text-sm rounded border border-[#D5CDBD]"
              />
            </div>
            <div>
              <label className="block text-[11px] text-[#546A6B] mb-1">Type</label>
              <select
                value={form.correction_type}
                onChange={(e) => setForm({ ...form, correction_type: e.target.value })}
                className="w-full px-3 py-2 text-sm rounded border border-[#D5CDBD]"
              >
                <option value="missed_check_in">Missed Check-In</option>
                <option value="missed_check_out">Missed Check-Out</option>
                <option value="time_adjustment">Time Adjustment</option>
              </select>
            </div>
            <div>
              <label className="block text-[11px] text-[#546A6B] mb-1">
                Requested Check-In
              </label>
              <input
                type="datetime-local"
                value={form.requested_check_in_at}
                onChange={(e) =>
                  setForm({ ...form, requested_check_in_at: e.target.value })
                }
                className="w-full px-3 py-2 text-sm rounded border border-[#D5CDBD]"
              />
            </div>
            <div>
              <label className="block text-[11px] text-[#546A6B] mb-1">
                Requested Check-Out
              </label>
              <input
                type="datetime-local"
                value={form.requested_check_out_at}
                onChange={(e) =>
                  setForm({ ...form, requested_check_out_at: e.target.value })
                }
                className="w-full px-3 py-2 text-sm rounded border border-[#D5CDBD]"
              />
            </div>
          </div>
          <textarea
            required
            rows={2}
            placeholder="Explain why the correction is needed..."
            value={form.reason}
            onChange={(e) => setForm({ ...form, reason: e.target.value })}
            className="w-full px-3 py-2 text-sm rounded border border-[#D5CDBD]"
          />
          <button
            type="submit"
            className="px-4 py-2 rounded bg-[#FFD400] text-[#0F3D3E] text-sm font-semibold hover:bg-[#E6BF00]"
          >
            Submit Correction Request
          </button>
        </form>
      )}

      <div className="bg-white rounded-lg border border-[#D5CDBD] overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[#F4F1EA] text-xs uppercase text-[#0F3D3E]">
            <tr>
              <th className="text-left px-5 py-3">Employee</th>
              <th className="text-left px-5 py-3">Target Date</th>
              <th className="text-left px-5 py-3">Type</th>
              <th className="text-left px-5 py-3">Reason</th>
              <th className="text-left px-5 py-3">Status</th>
              {canApprove && <th className="text-right px-5 py-3">Actions</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-[#EAE5DC]">
            {requests.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-5 py-8 text-center text-xs text-[#546A6B]">
                  No correction requests found.
                </td>
              </tr>
            ) : (
              requests.map((r) => (
                <tr key={r.id}>
                  <td className="px-5 py-3">
                    <div className="font-medium">{r.employee_name}</div>
                    <div className="text-xs text-[#546A6B]">{r.employee_code}</div>
                  </td>
                  <td className="px-5 py-3">{r.target_date}</td>
                  <td className="px-5 py-3 capitalize">
                    {r.correction_type.replace(/_/g, " ")}
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
