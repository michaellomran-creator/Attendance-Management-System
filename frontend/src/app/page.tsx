"use client";

import Link from "next/link";
import { ArrowRight, Building2, Clock, MonitorSmartphone, ShieldCheck } from "lucide-react";

export default function HomePage() {
  return (
    <div className="min-h-screen flex flex-col bg-[#F4F1EA] text-[#132425]">
      {/* Top Bar — Abyss Teal */}
      <header className="bg-[#0F3D3E] text-white border-b border-[#1A5658]">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded bg-[#FFD400] text-[#0F3D3E] font-bold flex items-center justify-center">
              N
            </div>
            <div>
              <span className="font-semibold tracking-tight">NORAM Attendance</span>
              <span className="hidden sm:inline text-xs text-[#B8D0D0] ml-2">
                by NORAM DIGITAL SOLUTIONS
              </span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/terminal"
              className="px-3.5 py-2 rounded-md text-sm font-medium text-[#FFD400] hover:bg-[#165254] transition-colors"
            >
              Attendance Terminal
            </Link>
            <Link
              href="/login"
              className="px-4 py-2 rounded-md text-sm font-semibold bg-[#FFD400] text-[#0F3D3E] hover:bg-[#E6BF00] transition-colors"
            >
              Sign In
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <main className="flex-1 max-w-6xl mx-auto px-6 py-16 w-full">
        <div className="bg-[#0F3D3E] text-white rounded-xl p-8 lg:p-12 border border-[#1A5658]">
          <div className="max-w-2xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#165254] text-[#FFD400] text-xs font-medium mb-6">
              <ShieldCheck className="w-3.5 h-3.5" />
              Multi-Organization Workforce Attendance Platform
            </div>
            <h1 className="text-3xl lg:text-4xl font-bold tracking-tight leading-tight mb-4">
              Reliable workforce attendance, shift scheduling, and compliance reporting.
            </h1>
            <p className="text-[#D7E4E4] text-base leading-relaxed mb-8">
              Built for hotels, hospitals, factories, offices, schools, and retail teams.
              Strict organization isolation, Employee ID + PIN kiosk terminals, overnight shift
              calculations, and auditable approvals.
            </p>
            <div className="flex flex-wrap gap-4">
              <Link
                href="/login"
                className="inline-flex items-center gap-2 px-5 py-3 rounded-md bg-[#FFD400] text-[#0F3D3E] font-semibold text-sm hover:bg-[#E6BF00] transition-colors"
              >
                <span>Open Management Portal</span>
                <ArrowRight className="w-4 h-4" />
              </Link>
              <Link
                href="/terminal"
                className="inline-flex items-center gap-2 px-5 py-3 rounded-md bg-[#165254] text-white font-medium text-sm border border-[#257173] hover:bg-[#1C6466] transition-colors"
              >
                <MonitorSmartphone className="w-4 h-4 text-[#FFD400]" />
                <span>Launch Kiosk Terminal</span>
              </Link>
            </div>
          </div>
        </div>

        {/* 3 Core Pillars */}
        <div className="grid md:grid-cols-3 gap-6 mt-10">
          <div className="bg-white p-6 rounded-lg border border-[#D5CDBD]">
            <div className="w-10 h-10 rounded-md bg-[#0F3D3E] text-[#FFD400] flex items-center justify-center mb-4">
              <MonitorSmartphone className="w-5 h-5" />
            </div>
            <h2 className="text-base font-semibold text-[#0F3D3E] mb-2">
              Fast ID + PIN Terminal
            </h2>
            <p className="text-sm text-[#546A6B] leading-relaxed">
              No biometric hardware required. Employees check in and out in seconds on any shared
              tablet or desktop with server-authoritative timestamps.
            </p>
          </div>

          <div className="bg-white p-6 rounded-lg border border-[#D5CDBD]">
            <div className="w-10 h-10 rounded-md bg-[#0F3D3E] text-[#FFD400] flex items-center justify-center mb-4">
              <Clock className="w-5 h-5" />
            </div>
            <h2 className="text-base font-semibold text-[#0F3D3E] mb-2">
              Overnight Shifts & Policies
            </h2>
            <p className="text-sm text-[#546A6B] leading-relaxed">
              Configurable grace periods, break tracking, overtime rules, and midnight-crossing
              night shifts calculated accurately per organization.
            </p>
          </div>

          <div className="bg-white p-6 rounded-lg border border-[#D5CDBD]">
            <div className="w-10 h-10 rounded-md bg-[#0F3D3E] text-[#FFD400] flex items-center justify-center mb-4">
              <Building2 className="w-5 h-5" />
            </div>
            <h2 className="text-base font-semibold text-[#0F3D3E] mb-2">
              Strict Tenant Isolation
            </h2>
            <p className="text-sm text-[#546A6B] leading-relaxed">
              Each organization operates in complete isolation with its own departments, locations,
              shifts, policies, and exportable reports.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
