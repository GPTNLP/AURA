import { createContext, useContext, useMemo, useState, useCallback } from "react";
import type { ReactNode } from "react";

export type Role = "admin" | "ta" | "student";

interface User {
  email: string;
  role: Role;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  authReady: boolean;

  // Admin flow
  adminStartLogin: (email: string, password: string) => Promise<void>;
  adminVerifyOtp: (email: string, otp: string) => Promise<void>;

  // TA flow
  taStartLogin: (email: string) => Promise<void>;
  taVerifyOtp: (email: string, otp: string) => Promise<void>;

  // Student flow
  studentStartLogin: (email: string) => Promise<void>;
  studentVerifyOtp: (email: string, otp: string) => Promise<void>;

  refreshMe: () => Promise<User | null>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType>(null as any);

const LS_TOKEN = "aura-auth-token";
const LS_USER = "aura-user";

const API_BASE =
  (import.meta.env.VITE_AUTH_API_BASE as string | undefined) ||
  (import.meta.env.VITE_CAMERA_API_BASE as string | undefined);

if (!API_BASE) {
  throw new Error("Missing VITE_AUTH_API_BASE in production build.");
}

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
  const [authReady, setAuthReady] = useState(false);

  const setSession = useCallback((t: string, u: User) => {
    setToken(t);
    setUser(u);
    localStorage.setItem(LS_TOKEN, t);
    localStorage.setItem(LS_USER, JSON.stringify(u));
  }, []);

  const clearSession = useCallback(() => {
    setToken(null);
    setUser(null);
    localStorage.removeItem(LS_TOKEN);
    localStorage.removeItem(LS_USER);
  }, []);

  const refreshMe = useCallback(async (): Promise<User | null> => {
    const currentToken = localStorage.getItem(LS_TOKEN);

    if (!currentToken) {
      clearSession();
      return null;
    }

    try {
      const res = await fetch(`${API_BASE}/auth/me`, {
        headers: authHeaders(currentToken),
        credentials: "include",
      });

      if (!res.ok) {
        clearSession();
        return null;
      }

      const data = await res.json().catch(() => null);
      const nextUser = data?.user as User | undefined;

      if (!nextUser?.email || !nextUser?.role) {
        clearSession();
        return null;
      }

      setToken(currentToken);
      setUser(nextUser);
      localStorage.setItem(LS_USER, JSON.stringify(nextUser));
      return nextUser;
    } catch {
      clearSession();
      return null;
    }
  }, [clearSession]);

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

  const logout = useCallback(() => {
    clearSession();
  }, [clearSession]);

  const bootstrapAuth = useCallback(async () => {
    if (!localStorage.getItem(LS_TOKEN)) {
      clearSession();
      setAuthReady(true);
      return;
    }

    await refreshMe();
    setAuthReady(true);
  }, [clearSession, refreshMe]);

  useMemo(() => {
    void bootstrapAuth();
  }, [bootstrapAuth]);

  const value = useMemo(
    () => ({
      user,
      token,
      authReady,
      adminStartLogin,
      adminVerifyOtp,
      studentStartLogin,
      studentVerifyOtp,
      taStartLogin,
      taVerifyOtp,
      refreshMe,
      logout,
    }),
    [user, token, authReady, refreshMe, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);