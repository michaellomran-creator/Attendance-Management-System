"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Download } from "lucide-react";
import { AppShell } from "@/components/ui/AppShell";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ApiError, apiDownload, apiFetch } from "@/lib/api";

export default function ReportsPage() {
  const [tab, setTab] = useState<"daily" | "monthly">("daily");
  const [reportDate, setReportDate] = useState("2026-01-01");
  const [year, setYear] = useState(2026);
  const [month, setMonth] = useState(1);
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const today = new Date();
    setReportDate(today.toISOString().slice(0, 10));
    setYear(today.getFullYear());
    setMonth(today.getMonth() + 1);
  }, []);

  const loadReport = useCallback(async () => {
    setError(null);
    try {
      if (tab === "daily") {
        const data = await apiFetch<Record<string, unknown>[]>(
          `/reports/daily?report_date=${reportDate}`
        );
        setRows(data);
      } else {
        const data = await apiFetch<Record<string, unknown>[]>(
          `/reports/monthly?year=${year}&month=${month}`
        );
        setRows(data);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load report");
    }
  }, [tab, reportDate, year, month]);

  useEffect(() => {
    loadReport();
  }, [loadReport]);

  const handleExport = async (format: "csv" | "xlsx") => {
    try {
      if (tab === "daily") {
        await apiDownload(
          `/reports/daily/export?report_date=${reportDate}&format=${format}`,
          `daily_attendance_${reportDate}.${format}`
        );
      } else {
        await apiDownload(
          `/reports/monthly/export?year=${year}&month=${month}&format=${format}`,
          `monthly_attendance_${year}_${month}.${format}`
        );
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Export failed");
    }
  };

  return (
    <AppShell
      title="Reports & Exports"
      subtitle="Generate daily and monthly attendance reports in CSV and Excel formats"
    >
      {error && (
        <div className="mb-4 p-3 rounded bg-red-50 border border-red-200 text-xs text-red-800">
          {error}
        </div>
      )}

      <div className="bg-white rounded-lg border border-[#D5CDBD] p-4 mb-6 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setTab("daily")}
            className={`px-4 py-2 rounded-md text-sm font-medium ${
              tab === "daily"
                ? "bg-[#0F3D3E] text-white"
                : "bg-[#F4F1EA] text-[#0F3D3E]"
            }`}
          >
            Daily Report
          </button>
          <button
            onClick={() => setTab("monthly")}
            className={`px-4 py-2 rounded-md text-sm font-medium ${
              tab === "monthly"
                ? "bg-[#0F3D3E] text-white"
                : "bg-[#F4F1EA] text-[#0F3D3E]"
            }`}
          >
            Monthly Summary
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {tab === "daily" ? (
            <input
              type="date"
              value={reportDate}
              onChange={(e) => setReportDate(e.target.value)}
              className="px-3 py-2 text-sm rounded border border-[#D5CDBD]"
            />
          ) : (
            <div className="flex gap-2">
              <input
                type="number"
                value={year}
                onChange={(e) => setYear(Number(e.target.value))}
                className="w-24 px-3 py-2 text-sm rounded border border-[#D5CDBD]"
              />
              <select
                value={month}
                onChange={(e) => setMonth(Number(e.target.value))}
                className="px-3 py-2 text-sm rounded border border-[#D5CDBD]"
              >
                {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                  <option key={m} value={m}>
                    Month {m}
                  </option>
                ))}
              </select>
            </div>
          )}

          <button
            onClick={() => handleExport("csv")}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded border border-[#0F3D3E] text-[#0F3D3E] text-sm font-medium hover:bg-[#F4F1EA]"
          >
            <Download className="w-4 h-4" /> CSV
          </button>
          <button
            onClick={() => handleExport("xlsx")}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded bg-[#FFD400] text-[#0F3D3E] text-sm font-semibold hover:bg-[#E6BF00]"
          >
            <Download className="w-4 h-4" /> Excel (.xlsx)
          </button>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-[#D5CDBD] overflow-hidden">
        <div className="overflow-x-auto">
          {rows.length === 0 ? (
            <div className="p-8 text-center text-xs text-[#546A6B]">
              No report data for the selected period.
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-[#F4F1EA] text-xs uppercase text-[#0F3D3E]">
                <tr>
                  {Object.keys(rows[0]).map((col) => (
                    <th key={col} className="text-left px-4 py-3">
                      {col.replace(/_/g, " ")}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[#EAE5DC]">
                {rows.map((row, idx) => (
                  <tr key={idx}>
                    {Object.entries(row).map(([key, val]) => (
                      <td key={key} className="px-4 py-3">
                        {key === "status" ? (
                          <StatusBadge status={String(val)} />
                        ) : (
                          String(val ?? "—")
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </AppShell>
  );
}
