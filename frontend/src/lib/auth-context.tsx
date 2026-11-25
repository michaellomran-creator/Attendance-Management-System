"use client";

import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import {
  apiFetch,
  clearStoredTokens,
  getStoredTokens,
  setStoredTokens,
} from "@/lib/api";

export interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  organization_id: string | null;
  organization_name: string | null;
  organization_timezone: string | null;
  is_platform_admin: boolean;
  roles: string[];
  permissions: string[];
  assigned_department_ids: string[];
  employee_id: string | null;
  employee_code: string | null;
  must_change_password: boolean;
}

interface AuthContextValue {
  user: UserProfile | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<UserProfile>;
  logout: () => void;
  hasPermission: (perm: string) => boolean;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshProfile = useCallback(async () => {
    const { access } = getStoredTokens();
    if (!access) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const profile = await apiFetch<UserProfile>("/auth/me");
      setUser(profile);
    } catch {
      clearStoredTokens();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshProfile();
  }, [refreshProfile]);

  const login = async (email: string, password: string): Promise<UserProfile> => {
    const data = await apiFetch<{
      access_token: string;
      refresh_token: string;
      user: UserProfile;
    }>("/auth/login", {
      method: "POST",
      skipAuth: true,
      body: JSON.stringify({ email, password }),
    });
    setStoredTokens(data.access_token, data.refresh_token);
    setUser(data.user);
    return data.user;
  };

  const logout = () => {
    clearStoredTokens();
    setUser(null);
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
  };

  const hasPermission = (perm: string) => {
    if (!user) return false;
    return user.permissions.includes(perm);
  };

  return (
    <AuthContext.Provider
      value={{ user, loading, login, logout, hasPermission, refreshProfile }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return ctx;
}
