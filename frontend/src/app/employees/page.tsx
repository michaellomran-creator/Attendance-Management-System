"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Download, Plus, Search, Upload, X } from "lucide-react";
import { AppShell } from "@/components/ui/AppShell";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ApiError, apiDownload, apiFetch } from "@/lib/api";

interface Employee {
  id: string;
  employee_code: string;
  first_name: string;
  last_name: string;
  email: string | null;
  phone_number: string;
  department_name: string | null;
  location_name: string | null;
  employment_type: string;
  employment_status: string;
  employment_start_date: string;
}

interface Department {
  id: string;
  name: string;
}

interface Location {
  id: string;
  name: string;
}

export default function EmployeesPage() {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [deptFilter, setDeptFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [departments, setDepartments] = useState<Department[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [form, setForm] = useState({
    employee_code: "",
    first_name: "",
    last_name: "",
    phone_number: "",
    email: "",
    department_id: "",
    location_id: "",
    employment_type: "full_time",
    employment_start_date: "",
    pin: "",
    create_user_account: false,
    user_password: "",
  });

  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [importPreview, setImportPreview] = useState<{
    valid_count: number;
    error_count: number;
    errors: { row_number: number; employee_code: string | null; error: string }[];
  } | null>(null);

  const loadData = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (search.trim()) params.set("search", search.trim());
      if (deptFilter) params.set("department_id", deptFilter);
      if (statusFilter) params.set("employment_status", statusFilter);

      const [empData, deptData, locData] = await Promise.all([
        apiFetch<{ items: Employee[]; total: number }>(`/employees?${params.toString()}`),
        apiFetch<Department[]>("/organizations/departments"),
        apiFetch<Location[]>("/organizations/locations"),
      ]);
      setEmployees(empData.items);
      setTotal(empData.total);
      setDepartments(deptData);
      setLocations(locData);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load employees");
    }
  }, [search, deptFilter, statusFilter]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await apiFetch("/employees", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          email: form.email || null,
          department_id: form.department_id || null,
          location_id: form.location_id || null,
          user_password: form.create_user_account ? form.user_password || null : null,
        }),
      });
      setShowCreate(false);
      setForm({
        employee_code: "",
        first_name: "",
        last_name: "",
        phone_number: "",
        email: "",
        department_id: "",
        location_id: "",
        employment_type: "full_time",
        employment_start_date: new Date().toISOString().slice(0, 10),
        pin: "",
        create_user_account: false,
        user_password: "",
      });
      await loadData();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to register employee");
    }
  };

  const handlePreviewCsv = async () => {
    if (!csvFile) return;
    setError(null);
    const fd = new FormData();
    fd.append("file", csvFile);
    try {
      const preview = await apiFetch<{
        valid_count: number;
        error_count: number;
        errors: { row_number: number; employee_code: string | null; error: string }[];
      }>("/employees/import/preview", { method: "POST", body: fd });
      setImportPreview(preview);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "CSV preview failed");
    }
  };

  const handleConfirmCsv = async () => {
    if (!csvFile) return;
    const fd = new FormData();
    fd.append("file", csvFile);
    try {
      await apiFetch("/employees/import/confirm", { method: "POST", body: fd });
      setShowImport(false);
      setCsvFile(null);
      setImportPreview(null);
      await loadData();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "CSV import failed");
    }
  };

  return (
    <AppShell title="Employee Directory" subtitle={`${total} employees in organization`}>
      {error && (
        <div className="mb-4 p-3 rounded bg-red-50 border border-red-200 text-xs text-red-800">
          {error}
        </div>
      )}

      {/* Toolbar */}
      <div className="bg-white rounded-lg border border-[#D5CDBD] p-4 mb-6 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3 flex-1">
          <div className="relative min-w-[220px] flex-1 max-w-xs">
            <Search className="w-4 h-4 text-[#546A6B] absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search name, ID, phone..."
              className="w-full pl-9 pr-3 py-2 text-sm rounded-md border border-[#D5CDBD] bg-[#FAF9F6] focus:outline-none focus:border-[#0F3D3E]"
            />
          </div>

          <select
            value={deptFilter}
            onChange={(e) => setDeptFilter(e.target.value)}
            className="px-3 py-2 text-sm rounded-md border border-[#D5CDBD] bg-[#FAF9F6]"
          >
            <option value="">All Departments</option>
            {departments.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2 text-sm rounded-md border border-[#D5CDBD] bg-[#FAF9F6]"
          >
            <option value="">All Statuses</option>
            <option value="active">Active</option>
            <option value="on_leave">On Leave</option>
            <option value="inactive">Inactive</option>
            <option value="suspended">Suspended</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowImport(true)}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-md border border-[#C9C0B1] bg-[#F4F1EA] text-[#0F3D3E] text-sm font-medium hover:bg-[#E6E0D4]"
          >
            <Upload className="w-4 h-4" /> Bulk CSV
          </button>
          <button
            onClick={() => setShowCreate(true)}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md bg-[#FFD400] text-[#0F3D3E] text-sm font-semibold hover:bg-[#E6BF00]"
          >
            <Plus className="w-4 h-4" /> Register Employee
          </button>
        </div>
      </div>

      {/* Directory Table */}
      <div className="bg-white rounded-lg border border-[#D5CDBD] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[#F4F1EA] text-[#0F3D3E] text-xs uppercase">
              <tr>
                <th className="text-left px-5 py-3">Employee ID</th>
                <th className="text-left px-5 py-3">Full Name</th>
                <th className="text-left px-5 py-3">Department</th>
                <th className="text-left px-5 py-3">Location</th>
                <th className="text-left px-5 py-3">Phone</th>
                <th className="text-left px-5 py-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#EAE5DC]">
              {employees.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-5 py-8 text-center text-xs text-[#546A6B]">
                    No employees found. Register an employee to get started.
                  </td>
                </tr>
              ) : (
                employees.map((emp) => (
                  <tr key={emp.id} className="hover:bg-[#FAF9F6]">
                    <td className="px-5 py-3 font-mono text-xs font-semibold text-[#0F3D3E]">
                      {emp.employee_code}
                    </td>
                    <td className="px-5 py-3 font-medium">
                      {emp.first_name} {emp.last_name}
                    </td>
                    <td className="px-5 py-3 text-[#546A6B]">
                      {emp.department_name || "Unassigned"}
                    </td>
                    <td className="px-5 py-3 text-[#546A6B]">
                      {emp.location_name || "Default"}
                    </td>
                    <td className="px-5 py-3 text-[#546A6B]">{emp.phone_number}</td>
                    <td className="px-5 py-3">
                      <StatusBadge status={emp.employment_status} />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Register Employee Modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg border border-[#D5CDBD] max-w-lg w-full p-6 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold text-[#0F3D3E]">
                Register Employee
              </h2>
              <button onClick={() => setShowCreate(false)}>
                <X className="w-5 h-5 text-[#546A6B]" />
              </button>
            </div>
            <form onSubmit={handleCreate} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-[#0F3D3E] mb-1">
                    Employee ID *
                  </label>
                  <input
                    required
                    value={form.employee_code}
                    onChange={(e) => setForm({ ...form, employee_code: e.target.value })}
                    placeholder="EMP-101"
                    className="w-full px-3 py-2 text-sm rounded border border-[#D5CDBD]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-[#0F3D3E] mb-1">
                    Attendance PIN (4-12 digits) *
                  </label>
                  <input
                    required
                    type="password"
                    pattern="[0-9]{4,12}"
                    value={form.pin}
                    onChange={(e) => setForm({ ...form, pin: e.target.value })}
                    placeholder="1234"
                    className="w-full px-3 py-2 text-sm rounded border border-[#D5CDBD]"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-[#0F3D3E] mb-1">
                    First Name *
                  </label>
                  <input
                    required
                    value={form.first_name}
                    onChange={(e) => setForm({ ...form, first_name: e.target.value })}
                    className="w-full px-3 py-2 text-sm rounded border border-[#D5CDBD]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-[#0F3D3E] mb-1">
                    Last Name *
                  </label>
                  <input
                    required
                    value={form.last_name}
                    onChange={(e) => setForm({ ...form, last_name: e.target.value })}
                    className="w-full px-3 py-2 text-sm rounded border border-[#D5CDBD]"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-[#0F3D3E] mb-1">
                    Phone Number *
                  </label>
                  <input
                    required
                    value={form.phone_number}
                    onChange={(e) => setForm({ ...form, phone_number: e.target.value })}
                    placeholder="+251911..."
                    className="w-full px-3 py-2 text-sm rounded border border-[#D5CDBD]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-[#0F3D3E] mb-1">
                    Start Date *
                  </label>
                  <input
                    required
                    type="date"
                    value={form.employment_start_date}
                    onChange={(e) =>
                      setForm({ ...form, employment_start_date: e.target.value })
                    }
                    className="w-full px-3 py-2 text-sm rounded border border-[#D5CDBD]"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-[#0F3D3E] mb-1">
                    Department
                  </label>
                  <select
                    value={form.department_id}
                    onChange={(e) => setForm({ ...form, department_id: e.target.value })}
                    className="w-full px-3 py-2 text-sm rounded border border-[#D5CDBD]"
                  >
                    <option value="">Unassigned</option>
                    {departments.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-[#0F3D3E] mb-1">
                    Location
                  </label>
                  <select
                    value={form.location_id}
                    onChange={(e) => setForm({ ...form, location_id: e.target.value })}
                    className="w-full px-3 py-2 text-sm rounded border border-[#D5CDBD]"
                  >
                    <option value="">Default</option>
                    {locations.map((l) => (
                      <option key={l.id} value={l.id}>
                        {l.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="pt-2">
                <label className="inline-flex items-center gap-2 text-xs font-medium text-[#0F3D3E]">
                  <input
                    type="checkbox"
                    checked={form.create_user_account}
                    onChange={(e) =>
                      setForm({ ...form, create_user_account: e.target.checked })
                    }
                  />
                  Create web dashboard login for this employee
                </label>
              </div>

              {form.create_user_account && (
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-[#0F3D3E] mb-1">
                      Email *
                    </label>
                    <input
                      type="email"
                      required
                      value={form.email}
                      onChange={(e) => setForm({ ...form, email: e.target.value })}
                      className="w-full px-3 py-2 text-sm rounded border border-[#D5CDBD]"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-[#0F3D3E] mb-1">
                      Password *
                    </label>
                    <input
                      type="password"
                      required
                      minLength={8}
                      value={form.user_password}
                      onChange={(e) => setForm({ ...form, user_password: e.target.value })}
                      className="w-full px-3 py-2 text-sm rounded border border-[#D5CDBD]"
                    />
                  </div>
                </div>
              )}

              <div className="flex justify-end gap-2 pt-3">
                <button
                  type="button"
                  onClick={() => setShowCreate(false)}
                  className="px-4 py-2 rounded border border-[#D5CDBD] text-sm"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded bg-[#FFD400] text-[#0F3D3E] font-semibold text-sm hover:bg-[#E6BF00]"
                >
                  Save Employee
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Bulk CSV Import Modal */}
      {showImport && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg border border-[#D5CDBD] max-w-lg w-full p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold text-[#0F3D3E]">
                Bulk CSV Employee Import
              </h2>
              <button onClick={() => setShowImport(false)}>
                <X className="w-5 h-5 text-[#546A6B]" />
              </button>
            </div>

            <div className="space-y-4">
              <button
                type="button"
                onClick={() =>
                  apiDownload("/employees/import/template", "employee_import_template.csv")
                }
                className="inline-flex items-center gap-2 text-xs font-medium text-[#0F3D3E] underline"
              >
                <Download className="w-4 h-4" /> Download CSV Template
              </button>

              <input
                type="file"
                accept=".csv"
                onChange={(e) => {
                  setCsvFile(e.target.files?.[0] || null);
                  setImportPreview(null);
                }}
                className="block w-full text-sm"
              />

              {importPreview && (
                <div className="p-3 rounded bg-[#F4F1EA] border border-[#D5CDBD] text-xs space-y-1">
                  <div>
                    Valid rows: <strong>{importPreview.valid_count}</strong> • Errors:{" "}
                    <strong>{importPreview.error_count}</strong>
                  </div>
                  {importPreview.errors.map((err, i) => (
                    <div key={i} className="text-red-700">
                      Row {err.row_number} ({err.employee_code || "N/A"}): {err.error}
                    </div>
                  ))}
                </div>
              )}

              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={handlePreviewCsv}
                  disabled={!csvFile}
                  className="px-4 py-2 rounded border border-[#0F3D3E] text-[#0F3D3E] text-sm font-medium disabled:opacity-50"
                >
                  Validate & Preview
                </button>
                <button
                  type="button"
                  onClick={handleConfirmCsv}
                  disabled={!importPreview || importPreview.error_count > 0 || importPreview.valid_count === 0}
                  className="px-4 py-2 rounded bg-[#FFD400] text-[#0F3D3E] text-sm font-semibold disabled:opacity-50"
                >
                  Confirm Import
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
