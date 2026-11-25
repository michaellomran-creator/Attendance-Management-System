"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Lock, Mail, MonitorSmartphone } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { ApiError } from "@/lib/api";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const profile = await login(email, password);
      if (profile.is_platform_admin) {
        router.push("/platform");
      } else {
        router.push("/dashboard");
      }
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Unable to sign in. Please try again."
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col lg:flex-row bg-[#F4F1EA]">
      {/* Left Brand Panel — Abyss Teal */}
      <div className="lg:w-5/12 bg-[#0F3D3E] text-white p-8 lg:p-12 flex flex-col justify-between">
        <div>
          <Link href="/" className="inline-flex items-center gap-2.5">
            <div className="w-9 h-9 rounded bg-[#FFD400] text-[#0F3D3E] font-bold flex items-center justify-center">
              N
            </div>
            <span className="text-lg font-semibold tracking-tight">NORAM Attendance</span>
          </Link>
        </div>

        <div className="my-12">
          <h1 className="text-2xl lg:text-3xl font-bold leading-snug mb-3">
            Workforce Attendance & Shift Operations
          </h1>
          <p className="text-sm text-[#D7E4E4] leading-relaxed max-w-md">
            Sign in to manage organization attendance, configure shifts and policies, review
            leave and correction requests, or administer platform tenants.
          </p>
        </div>

        <div className="pt-6 border-t border-[#1A5658] flex items-center justify-between text-xs text-[#B8D0D0]">
          <span>NORAM DIGITAL SOLUTIONS</span>
          <Link
            href="/terminal"
            className="inline-flex items-center gap-1.5 text-[#FFD400] hover:underline font-medium"
          >
            <MonitorSmartphone className="w-3.5 h-3.5" />
            Kiosk Terminal
          </Link>
        </div>
      </div>

      {/* Right Login Form — Sand Putty */}
      <div className="flex-1 flex items-center justify-center p-6 lg:p-12">
        <div className="w-full max-w-md bg-white rounded-lg border border-[#D5CDBD] p-8 shadow-sm">
          <h2 className="text-xl font-semibold text-[#0F3D3E] mb-1">
            Sign in to your account
          </h2>
          <p className="text-xs text-[#546A6B] mb-6">
            Enter your organization or platform credentials.
          </p>

          {error && (
            <div className="mb-4 p-3 rounded-md bg-red-50 border border-red-200 text-xs text-red-800">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-[#0F3D3E] mb-1.5">
                Email address
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 text-[#546A6B] absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@organization.com"
                  className="w-full pl-9 pr-3 py-2.5 text-sm rounded-md border border-[#D5CDBD] bg-[#FAF9F6] focus:outline-none focus:border-[#0F3D3E]"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-[#0F3D3E] mb-1.5">
                Password
              </label>
              <div className="relative">
                <Lock className="w-4 h-4 text-[#546A6B] absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full pl-9 pr-3 py-2.5 text-sm rounded-md border border-[#D5CDBD] bg-[#FAF9F6] focus:outline-none focus:border-[#0F3D3E]"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="w-full py-2.5 px-4 rounded-md bg-[#FFD400] text-[#0F3D3E] font-semibold text-sm hover:bg-[#E6BF00] disabled:opacity-60 transition-colors"
            >
              {submitting ? "Signing in..." : "Sign In"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
