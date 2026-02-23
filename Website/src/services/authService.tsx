import { createContext, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";

export type Role = "admin" | "ta" | "student";

interface User {
  email: string;
  role: Role;
}

interface AuthContextType {
  user: User | null;
  token: string | null;

  // Admin flow (email + password -> otp)
  adminStartLogin: (email: string, password: string) => Promise<void>;
  adminVerifyOtp: (email: string, otp: string) => Promise<void>;

  // TA flow (email -> otp), TA-only endpoints
  taStartLogin: (email: string) => Promise<void>;
  taVerifyOtp: (email: string, otp: string) => Promise<void>;

  // Student flow (email -> otp), ALWAYS student
  studentStartLogin: (email: string) => Promise<void>;
  studentVerifyOtp: (email: string, otp: string) => Promise<void>;

  refreshMe: () => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType>(null as any);

const LS_TOKEN = "aura-auth-token";
const LS_USER = "aura-user";

const API_BASE =
  (import.meta.env.VITE_AUTH_API_BASE as string | undefined) ||
  (import.meta.env.VITE_CAMERA_API_BASE as string | undefined) ||
  "http://127.0.0.1:9000";

function authHeaders(token: string | null): HeadersInit {
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

async function readError(res: Response, fallback: string) {
  try {
    const j = await res.json();
    return j?.detail || j?.message || fallback;
  } catch {
    try {
      const t = await res.text();
      return t || fallback;
    } catch {
      return fallback;
    }
  }
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

    const res = await fetch(`${API_BASE}/auth/me`, {
      headers: authHeaders(token),
      credentials: "include",
    });

    if (res.ok) {
      const data = await res.json().catch(() => null);
      if (data?.user) {
        setUser(data.user as User);
        localStorage.setItem(LS_USER, JSON.stringify(data.user));
      }
      return;
    }

    clearSession();
  };

  // -----------------------
  // Admin OTP
  // -----------------------
  const adminStartLogin = async (email: string, password: string) => {
    const res = await fetch(`${API_BASE}/auth/admin/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ email: email.trim().toLowerCase(), password }),
    });

    if (!res.ok) throw new Error(await readError(res, "Admin login failed"));
  };

  const adminVerifyOtp = async (email: string, otp: string) => {
    const res = await fetch(`${API_BASE}/auth/admin/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ email: email.trim().toLowerCase(), otp: otp.trim() }),
    });

    if (!res.ok) throw new Error(await readError(res, "Invalid OTP"));

    const data = await res.json().catch(() => null);
    if (!data?.token || !data?.user) throw new Error("Server did not return a session token");

    setSession(data.token as string, data.user as User);
  };

  // -----------------------
  // Student OTP (ALWAYS student role)
  // -----------------------
  const studentStartLogin = async (email: string) => {
    const res = await fetch(`${API_BASE}/auth/student/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ email: email.trim().toLowerCase() }),
    });

    if (!res.ok) throw new Error(await readError(res, "Student login failed"));
  };

  const studentVerifyOtp = async (email: string, otp: string) => {
    const res = await fetch(`${API_BASE}/auth/student/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ email: email.trim().toLowerCase(), otp: otp.trim() }),
    });

    if (!res.ok) throw new Error(await readError(res, "Invalid OTP"));

    const data = await res.json().catch(() => null);
    if (!data?.token || !data?.user) throw new Error("Server did not return a session token");

    setSession(data.token as string, data.user as User);
  };

  // -----------------------
  // TA OTP (TA-only endpoints)
  // -----------------------
  const taStartLogin = async (email: string) => {
    const res = await fetch(`${API_BASE}/auth/ta/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ email: email.trim().toLowerCase() }),
    });

    if (!res.ok) throw new Error(await readError(res, "TA login failed"));
  };

  const taVerifyOtp = async (email: string, otp: string) => {
    const res = await fetch(`${API_BASE}/auth/ta/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ email: email.trim().toLowerCase(), otp: otp.trim() }),
    });

    if (!res.ok) throw new Error(await readError(res, "Invalid OTP"));

    const data = await res.json().catch(() => null);
    if (!data?.token || !data?.user) throw new Error("Server did not return a session token");

    setSession(data.token as string, data.user as User);
  };

  const logout = () => clearSession();

  const value = useMemo(
    () => ({
      user,
      token,
      adminStartLogin,
      adminVerifyOtp,
      studentStartLogin,
      studentVerifyOtp,
      taStartLogin,
      taVerifyOtp,
      refreshMe,
      logout,
    }),
    [user, token]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);