import { createContext, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";

interface User {
  email: string;
  role?: "admin" | "student";
}

interface AuthContextType {
  user: User | null;
  token: string | null;

  // Admin OTP flow
  adminStartLogin: (email: string, password: string) => Promise<void>;
  adminVerifyOtp: (email: string, otp: string) => Promise<void>;

  // Student OTP flow (no password)
  studentStart: (email: string) => Promise<void>;
  studentVerify: (email: string, otp: string) => Promise<void>;

  setSession: (token: string, user: User) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType>(null as any);

const LS_USER = "aura-user";
const LS_TOKEN = "aura-auth-token";

const API_BASE =
  import.meta.env.VITE_AUTH_API_BASE ||
  import.meta.env.VITE_CAMERA_API_BASE ||
  "http://127.0.0.1:9000";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    const stored = localStorage.getItem(LS_USER);
    return stored ? (JSON.parse(stored) as User) : null;
  });

  const [token, setToken] = useState<string | null>(() => {
    return localStorage.getItem(LS_TOKEN);
  });

  const setSession = (t: string, u: User) => {
    setToken(t);
    setUser(u);
    localStorage.setItem(LS_TOKEN, t);
    localStorage.setItem(LS_USER, JSON.stringify(u));
  };

  // -----------------------
  // Admin OTP
  // -----------------------
  const adminStartLogin = async (email: string, password: string) => {
    const res = await fetch(`${API_BASE}/auth/admin/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
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
      body: JSON.stringify({ email: email.trim(), otp: otp.trim() }),
    });

    if (!res.ok) {
      const msg = await res.text();
      throw new Error(msg || "Invalid OTP");
    }

    const data = await res.json();
    setSession(data.token, data.user);
  };

  // -----------------------
  // Student OTP (no password)
  // -----------------------
  const studentStart = async (email: string) => {
    const res = await fetch(`${API_BASE}/auth/student/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
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
      body: JSON.stringify({ email: email.trim(), otp: otp.trim() }),
    });

    if (!res.ok) {
      const msg = await res.text();
      throw new Error(msg || "Invalid OTP");
    }

    const data = await res.json();
    setSession(data.token, data.user);
  };

  const logout = () => {
    setUser(null);
    setToken(null);
    localStorage.removeItem(LS_USER);
    localStorage.removeItem(LS_TOKEN);
  };

  const value = useMemo(
    () => ({
      user,
      token,
      adminStartLogin,
      adminVerifyOtp,
      studentStart,
      studentVerify,
      setSession,
      logout,
    }),
    [user, token]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);