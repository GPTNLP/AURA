// src/services/authService.tsx
import { createContext, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";

interface User {
  email: string;
  role?: "admin" | "student";
}

interface AuthContextType {
  user: User | null;

  // Admin OTP flow
  adminStartLogin: (email: string, password: string) => Promise<void>;
  adminVerifyOtp: (email: string, otp: string) => Promise<void>;

  // Student OTP flow
  studentStart: (email: string) => Promise<void>;
  studentVerify: (email: string, otp: string) => Promise<void>;

  refreshMe: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>(null as any);

const API_BASE =
  import.meta.env.VITE_AUTH_API_BASE ||
  import.meta.env.VITE_CAMERA_API_BASE ||
  "http://127.0.0.1:9000";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);

  const refreshMe = async () => {
    const res = await fetch(`${API_BASE}/auth/admin/me`, {
      credentials: "include",
    });

    // If admin/me fails, try student/me if you have it (optional).
    if (res.ok) {
      const data = await res.json();
      setUser(data.user);
      return;
    }

    // Not logged in (or student route only). Just clear.
    setUser(null);
  };

  // -----------------------
  // Admin OTP
  // -----------------------
  const adminStartLogin = async (email: string, password: string) => {
    const res = await fetch(`${API_BASE}/auth/admin/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ email: email.trim(), password }),
    });

    if (!res.ok) {
      const msg = await res.text();
      throw new Error(msg || "Admin login failed");
    }
  };

  const adminVerifyOtp = async (email: string, otp: string) => {
    const res = await fetch(`${API_BASE}/auth/admin/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ email: email.trim(), otp: otp.trim() }),
    });

    if (!res.ok) {
      const msg = await res.text();
      throw new Error(msg || "Invalid OTP");
    }

    await refreshMe();
  };

  // -----------------------
  // Student OTP
  // -----------------------
  const studentStart = async (email: string) => {
    const res = await fetch(`${API_BASE}/auth/student/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ email: email.trim() }),
    });

    if (!res.ok) {
      const msg = await res.text();
      throw new Error(msg || "Student OTP start failed");
    }
  };

  const studentVerify = async (email: string, otp: string) => {
    const res = await fetch(`${API_BASE}/auth/student/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ email: email.trim(), otp: otp.trim() }),
    });

    if (!res.ok) {
      const msg = await res.text();
      throw new Error(msg || "Invalid OTP");
    }

    // If you add /auth/student/me later, call that here. For now:
    // If your backend returns user, you can setUser directly.
    const data = await res.json().catch(() => null);
    if (data?.user) setUser(data.user);
    else await refreshMe();
  };

  const logout = async () => {
    // Add a backend /auth/logout endpoint to clear cookie, recommended.
    // For now: just clear local state; cookie remains until expiry.
    setUser(null);
  };

  const value = useMemo(
    () => ({
      user,
      adminStartLogin,
      adminVerifyOtp,
      studentStart,
      studentVerify,
      refreshMe,
      logout,
    }),
    [user]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);