"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Bell,
  Building2,
  CalendarClock,
  ClipboardCheck,
  Clock,
  FileBarChart2,
  FileCheck2,
  LayoutDashboard,
  LogOut,
  Menu,
  MonitorSmartphone,
  Settings,
  ShieldCheck,
  Users,
  X,
} from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { apiFetch } from "@/lib/api";

interface NavItem {
  label: string;
  href: string;
  icon: typeof LayoutDashboard;
  permission?: string;
  platformOnly?: boolean;
  orgOnly?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  {
    label: "Platform Console",
    href: "/platform",
    icon: ShieldCheck,
    platformOnly: true,
  },
  {
    label: "Overview",
    href: "/dashboard",
    icon: LayoutDashboard,
    orgOnly: true,
  },
  {
    label: "Employees",
    href: "/employees",
    icon: Users,
    permission: "employee:read",
    orgOnly: true,
  },
  {
    label: "Shifts & Schedules",
    href: "/shifts",
    icon: CalendarClock,
    orgOnly: true,
  },
  {
    label: "Attendance Records",
    href: "/attendance",
    icon: Clock,
    orgOnly: true,
  },
  {
    label: "Leave Management",
    href: "/leave",
    icon: ClipboardCheck,
    orgOnly: true,
  },
  {
    label: "Corrections",
    href: "/corrections",
    icon: FileCheck2,
    orgOnly: true,
  },
  {
    label: "Reports & Exports",
    href: "/reports",
    icon: FileBarChart2,
    permission: "report:view",
    orgOnly: true,
  },
  {
    label: "Organization Settings",
    href: "/settings",
    icon: Settings,
    permission: "org:manage_settings",
    orgOnly: true,
  },
];

export function AppShell({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  const { user, loading, logout, hasPermission } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    }
  }, [loading, user, router]);

  useEffect(() => {
    if (user && !user.is_platform_admin) {
      apiFetch<{ is_read: boolean }[]>("/notifications")
        .then((items) => setUnreadCount(items.filter((i) => !i.is_read).length))
        .catch(() => {});
    }
  }, [user]);

  if (loading || !user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#F4F1EA]">
        <div className="text-sm font-medium text-[#0F3D3E]">Loading workspace...</div>
      </div>
    );
  }

  const visibleNav = NAV_ITEMS.filter((item) => {
    if (item.platformOnly && !user.is_platform_admin) return false;
    if (item.orgOnly && user.is_platform_admin) return false;
    if (item.permission && !hasPermission(item.permission)) return false;
    return true;
  });

  return (
    <div className="min-h-screen flex bg-[#F4F1EA]">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-30 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar — Abyss Teal (60% foundation) */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-64 bg-[#0F3D3E] text-[#F4F1EA] flex flex-col transition-transform duration-200 lg:static lg:translate-x-0 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="h-16 px-5 flex items-center justify-between border-b border-[#1A5658]">
          <Link href={user.is_platform_admin ? "/platform" : "/dashboard"} className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded bg-[#FFD400] text-[#0F3D3E] flex items-center justify-center font-bold text-sm">
              N
            </div>
            <div>
              <div className="text-sm font-semibold tracking-tight text-white">
                NORAM Attendance
              </div>
              <div className="text-[11px] text-[#B8D0D0] truncate max-w-[150px]">
                {user.is_platform_admin
                  ? "Platform Owner"
                  : user.organization_name || "Organization"}
              </div>
            </div>
          </Link>
          <button
            onClick={() => setSidebarOpen(false)}
            className="lg:hidden text-[#B8D0D0] hover:text-white"
            aria-label="Close navigation"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {visibleNav.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setSidebarOpen(false)}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors ${
                  active
                    ? "bg-[#FFD400] text-[#0F3D3E] font-semibold"
                    : "text-[#D7E4E4] hover:bg-[#165254] hover:text-white"
                }`}
              >
                <Icon className="w-4 h-4 shrink-0" />
                <span>{item.label}</span>
              </Link>
            );
          })}

          {!user.is_platform_admin && (
            <div className="pt-4 mt-4 border-t border-[#1A5658]">
              <Link
                href="/terminal"
                className="flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium text-[#FFD400] hover:bg-[#165254]"
              >
                <MonitorSmartphone className="w-4 h-4 shrink-0" />
                <span>Attendance Terminal</span>
              </Link>
            </div>
          )}
        </nav>

        <div className="p-4 border-t border-[#1A5658] bg-[#0A2B2C]">
          <div className="flex items-center justify-between">
            <div className="min-w-0">
              <div className="text-xs font-semibold text-white truncate">
                {user.full_name}
              </div>
              <div className="text-[11px] text-[#9CBABA] truncate">
                {user.roles.join(", ")}
              </div>
            </div>
            <button
              onClick={logout}
              title="Sign out"
              className="p-2 rounded-md text-[#B8D0D0] hover:text-white hover:bg-[#165254]"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content Area — Sand Putty (30%) */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-16 bg-white border-b border-[#D5CDBD] px-4 lg:px-8 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(true)}
              className="lg:hidden p-2 rounded-md text-[#0F3D3E] hover:bg-[#F4F1EA]"
              aria-label="Open navigation"
            >
              <Menu className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-lg font-semibold text-[#0F3D3E] leading-tight">
                {title}
              </h1>
              {subtitle && (
                <p className="text-xs text-[#546A6B]">{subtitle}</p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-4">
            {user.organization_timezone && (
              <span className="hidden sm:inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded bg-[#F4F1EA] text-[#0F3D3E] border border-[#D5CDBD]">
                <Building2 className="w-3.5 h-3.5" />
                {user.organization_timezone}
              </span>
            )}
            {!user.is_platform_admin && (
              <Link
                href="/dashboard"
                className="relative p-2 rounded-md text-[#0F3D3E] hover:bg-[#F4F1EA]"
                title="Notifications"
              >
                <Bell className="w-5 h-5" />
                {unreadCount > 0 && (
                  <span className="absolute top-1 right-1 w-4 h-4 rounded-full bg-[#FFD400] text-[#0F3D3E] text-[10px] font-bold flex items-center justify-center">
                    {unreadCount}
                  </span>
                )}
              </Link>
            )}
          </div>
        </header>

        <main className="flex-1 p-4 lg:p-8 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
}
