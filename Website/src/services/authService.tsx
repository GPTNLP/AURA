// src/services/authService.tsx
import { createContext, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";

interface User {
  email: string;
  role?: "admin" | "student";
}

interface AuthContextType {
  user: User | null;
  token: string | null;

  adminStartLogin: (email: string, password: string) => Promise<void>;
  adminVerifyOtp: (email: string, otp: string) => Promise<void>;

  studentStart: (email: string) => Promise<void>;
  studentVerify: (email: string, otp: string) => Promise<void>;

  refreshMe: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>(null as any);

const LS_TOKEN = "aura-auth-token";
const LS_USER = "aura-user";

const API_BASE =
  import.meta.env.VITE_AUTH_API_BASE ||
  import.meta.env.VITE_CAMERA_API_BASE ||
  "http://127.0.0.1:9000";

function makeAuthHeaders(token: string | null): HeadersInit {
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(LS_TOKEN));
  const [user, setUser] = useState<User | null>(() => {
    const stored = localStorage.getItem(LS_USER);
    return stored ? (JSON.parse(stored) as User) : null;
  });

  const setSession = (t: string, u: User) => {
    setToken(t);
    setUser(u);
    localStorage.setItem(LS_TOKEN, t);
    localStorage.setItem(LS_USER, JSON.stringify(u));
  };

  const clearSession = () => {
    setToken(null);
    setUser(null);
    localStorage.removeItem(LS_TOKEN);
    localStorage.removeItem(LS_USER);
  };

  const refreshMe = async () => {
    if (!token) {
      setUser(null);
      return;
    }

    // try admin/me first
    let res = await fetch(`${API_BASE}/auth/admin/me`, {
      headers: makeAuthHeaders(token),
    });

    if (res.ok) {
      const data = await res.json();
      setUser(data.user);
      localStorage.setItem(LS_USER, JSON.stringify(data.user));
      return;
    }

    // then student/me (if implemented)
    res = await fetch(`${API_BASE}/auth/student/me`, {
      headers: makeAuthHeaders(token),
    });

    if (res.ok) {
      const data = await res.json();
      setUser(data.user);
      localStorage.setItem(LS_USER, JSON.stringify(data.user));
      return;
    }

    // token invalid/expired
    clearSession();
  };

  // -----------------------
  // Admin OTP
  // -----------------------
  const adminStartLogin = async (email: string, password: string) => {
    const res = await fetch(`${API_BASE}/auth/admin/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: email.trim().toLowerCase(),
        password,
      }),
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
      body: JSON.stringify({
        email: email.trim().toLowerCase(),
        otp: otp.trim(),
      }),
    });

    if (!res.ok) {
      const msg = await res.text();
      throw new Error(msg || "Invalid OTP");
    }

    const data = await res.json().catch(() => null);
    if (!data?.token || !data?.user) {
      throw new Error("Server did not return a session token");
    }

    setSession(data.token, data.user);
  };

  // -----------------------
  // Student OTP
  // -----------------------
  const studentStart = async (email: string) => {
    const res = await fetch(`${API_BASE}/auth/student/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: email.trim().toLowerCase() }),
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
      body: JSON.stringify({
        email: email.trim().toLowerCase(),
        otp: otp.trim(),
      }),
    });

    if (!res.ok) {
      const msg = await res.text();
      throw new Error(msg || "Invalid OTP");
    }

    const data = await res.json().catch(() => null);
    if (!data?.token || !data?.user) {
      throw new Error("Server did not return a session token");
    }

    setSession(data.token, data.user);
  };

  const logout = async () => {
    // optional: call backend logout (clears cookie if you use it)
    try {
      await fetch(`${API_BASE}/auth/admin/logout`, { method: "POST" });
    } catch {
      // ignore
    }
    try {
      await fetch(`${API_BASE}/auth/student/logout`, { method: "POST" });
    } catch {
      // ignore
    }
    clearSession();
  };

  const value = useMemo(
    () => ({
      user,
      token,
      adminStartLogin,
      adminVerifyOtp,
      studentStart,
      studentVerify,
      refreshMe,
      logout,
    }),
    [user, token]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);