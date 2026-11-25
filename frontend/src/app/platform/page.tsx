"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Building2, Plus, ShieldCheck } from "lucide-react";
import { AppShell } from "@/components/ui/AppShell";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ApiError, apiFetch } from "@/lib/api";

interface Plan {
  id: string;
  code: string;
  name: string;
  max_employees: number;
  monthly_price: number;
  currency: string;
}

interface Org {
  id: string;
  name: string;
  organization_type: string;
  contact_person: string;
  business_email: string;
  timezone: string;
  status: string;
  active_employees_count: number;
  subscription: {
    plan_name: string | null;
    status: string;
    payment_status: string;
    expiry_date: string;
  } | null;
}

interface Analytics {
  total_organizations: number;
  active_organizations: number;
  suspended_organizations: number;
  total_active_employees: number;
  total_attendance_sessions_today: number;
}

export default function PlatformAdminPage() {
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [orgs, setOrgs] = useState<Org[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [showOnboard, setShowOnboard] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [form, setForm] = useState({
    name: "",
    organization_type: "hotel",
    contact_person: "",
    business_email: "",
    phone_number: "",
    country: "Ethiopia",
    timezone: "Africa/Addis_Ababa",
    plan_id: "",
    admin_full_name: "",
    admin_email: "",
    admin_password: "",
  });

  const loadAll = useCallback(async () => {
    try {
      const [a, o, p] = await Promise.all([
        apiFetch<Analytics>("/platform/analytics"),
        apiFetch<Org[]>("/platform/organizations"),
        apiFetch<Plan[]>("/platform/plans"),
      ]);
      setAnalytics(a);
      setOrgs(o);
      setPlans(p);
      if (p.length > 0 && !form.plan_id) {
        setForm((prev) => ({ ...prev, plan_id: p[0].id }));
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load platform data");
    }
  }, [form.plan_id]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const handleOnboard = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await apiFetch("/platform/organizations", {
        method: "POST",
        body: JSON.stringify(form),
      });
      setShowOnboard(false);
      await loadAll();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Onboarding failed");
    }
  };

  const handleToggleOrgStatus = async (org: Org) => {
    const nextStatus = org.status === "active" ? "suspended" : "active";
    await apiFetch(`/platform/organizations/${org.id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status: nextStatus }),
    });
    await loadAll();
  };

  return (
    <AppShell
      title="Platform Owner Console"
      subtitle="Manage multi-organization tenants, subscriptions, and platform health"
    >
      {error && (
        <div className="mb-4 p-3 rounded bg-red-50 border border-red-200 text-xs text-red-800">
          {error}
        </div>
      )}

      {/* Platform KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div className="bg-[#0F3D3E] text-white rounded-lg p-4">
          <div className="text-xs text-[#D7E4E4]">Total Organizations</div>
          <div className="text-2xl font-bold mt-1">{analytics?.total_organizations ?? 0}</div>
        </div>
        <div className="bg-white border border-[#D5CDBD] rounded-lg p-4">
          <div className="text-xs text-[#546A6B]">Active Organizations</div>
          <div className="text-2xl font-bold text-[#0F3D3E] mt-1">
            {analytics?.active_organizations ?? 0}
          </div>
        </div>
        <div className="bg-white border border-[#D5CDBD] rounded-lg p-4">
          <div className="text-xs text-[#546A6B]">Total Active Employees</div>
          <div className="text-2xl font-bold text-[#0F3D3E] mt-1">
            {analytics?.total_active_employees ?? 0}
          </div>
        </div>
        <div className="bg-white border border-[#D5CDBD] rounded-lg p-4">
          <div className="text-xs text-[#546A6B]">Sessions Today</div>
          <div className="text-2xl font-bold text-[#0F3D3E] mt-1">
            {analytics?.total_attendance_sessions_today ?? 0}
          </div>
        </div>
      </div>

      <div className="flex justify-between items-center mb-4">
        <h2 className="text-sm font-semibold text-[#0F3D3E] flex items-center gap-2">
          <Building2 className="w-4 h-4" /> Registered Organizations
        </h2>
        <button
          onClick={() => setShowOnboard(!showOnboard)}
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md bg-[#FFD400] text-[#0F3D3E] text-sm font-semibold hover:bg-[#E6BF00]"
        >
          <Plus className="w-4 h-4" /> Onboard Organization
        </button>
      </div>

      {showOnboard && (
        <form
          onSubmit={handleOnboard}
          className="bg-white rounded-lg border border-[#D5CDBD] p-6 mb-6 space-y-4"
        >
          <h3 className="text-sm font-semibold text-[#0F3D3E] flex items-center gap-2">
            <ShieldCheck className="w-4 h-4" /> New Organization Onboarding
          </h3>
          <div className="grid sm:grid-cols-3 gap-3">
            <input
              required
              placeholder="Organization Name"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="px-3 py-2 text-sm rounded border border-[#D5CDBD]"
            />
            <select
              value={form.organization_type}
              onChange={(e) => setForm({ ...form, organization_type: e.target.value })}
              className="px-3 py-2 text-sm rounded border border-[#D5CDBD]"
            >
              <option value="hotel">Hotel / Hospitality</option>
              <option value="hospital">Hospital / Clinic</option>
              <option value="factory">Factory / Manufacturing</option>
              <option value="restaurant">Restaurant / Cafe</option>
              <option value="school">School / University</option>
              <option value="office">Office / Corporate</option>
              <option value="retail">Retail</option>
              <option value="construction">Construction</option>
              <option value="ngo">NGO / Institution</option>
            </select>
            <select
              required
              value={form.plan_id}
              onChange={(e) => setForm({ ...form, plan_id: e.target.value })}
              className="px-3 py-2 text-sm rounded border border-[#D5CDBD]"
            >
              {plans.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} (up to {p.max_employees} staff)
                </option>
              ))}
            </select>
            <input
              required
              placeholder="Contact Person"
              value={form.contact_person}
              onChange={(e) => setForm({ ...form, contact_person: e.target.value })}
              className="px-3 py-2 text-sm rounded border border-[#D5CDBD]"
            />
            <input
              required
              type="email"
              placeholder="Business Email"
              value={form.business_email}
              onChange={(e) => setForm({ ...form, business_email: e.target.value })}
              className="px-3 py-2 text-sm rounded border border-[#D5CDBD]"
            />
            <input
              required
              placeholder="Phone Number"
              value={form.phone_number}
              onChange={(e) => setForm({ ...form, phone_number: e.target.value })}
              className="px-3 py-2 text-sm rounded border border-[#D5CDBD]"
            />
            <input
              required
              placeholder="Initial Admin Full Name"
              value={form.admin_full_name}
              onChange={(e) => setForm({ ...form, admin_full_name: e.target.value })}
              className="px-3 py-2 text-sm rounded border border-[#D5CDBD]"
            />
            <input
              required
              type="email"
              placeholder="Initial Admin Email"
              value={form.admin_email}
              onChange={(e) => setForm({ ...form, admin_email: e.target.value })}
              className="px-3 py-2 text-sm rounded border border-[#D5CDBD]"
            />
            <input
              required
              type="password"
              minLength={8}
              placeholder="Initial Admin Password"
              value={form.admin_password}
              onChange={(e) => setForm({ ...form, admin_password: e.target.value })}
              className="px-3 py-2 text-sm rounded border border-[#D5CDBD]"
            />
          </div>
          <button
            type="submit"
            className="px-5 py-2 rounded bg-[#0F3D3E] text-white text-sm font-semibold"
          >
            Create Organization & Admin
          </button>
        </form>
      )}

      <div className="bg-white rounded-lg border border-[#D5CDBD] overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[#F4F1EA] text-xs uppercase text-[#0F3D3E]">
            <tr>
              <th className="text-left px-5 py-3">Organization</th>
              <th className="text-left px-5 py-3">Type</th>
              <th className="text-left px-5 py-3">Plan</th>
              <th className="text-left px-5 py-3">Employees</th>
              <th className="text-left px-5 py-3">Status</th>
              <th className="text-right px-5 py-3">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#EAE5DC]">
            {orgs.map((o) => (
              <tr key={o.id}>
                <td className="px-5 py-3">
                  <div className="font-medium text-[#0F3D3E]">{o.name}</div>
                  <div className="text-xs text-[#546A6B]">{o.business_email}</div>
                </td>
                <td className="px-5 py-3 capitalize">{o.organization_type}</td>
                <td className="px-5 py-3">{o.subscription?.plan_name || "—"}</td>
                <td className="px-5 py-3">{o.active_employees_count}</td>
                <td className="px-5 py-3">
                  <StatusBadge status={o.status} />
                </td>
                <td className="px-5 py-3 text-right">
                  <button
                    onClick={() => handleToggleOrgStatus(o)}
                    className="px-3 py-1 rounded border border-[#C9C0B1] text-xs font-medium hover:bg-[#F4F1EA]"
                  >
                    {o.status === "active" ? "Suspend" : "Activate"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </AppShell>
  );
}
