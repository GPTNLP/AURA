import {
  createContext,
  useContext,
  useMemo,
  useState,
  useCallback,
  useEffect,
} from "react";
import type { ReactNode } from "react";

export type Role = "admin" | "ta" | "student";

interface User {
  email: string;
  role: Role;
}

export interface PortalHint {
  has_admin_access?: boolean;
  has_ta_access?: boolean;
  notice?: string | null;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  authReady: boolean;

  adminStartLogin: (email: string, password: string) => Promise<void>;
  adminVerifyOtp: (email: string, otp: string) => Promise<void>;

  taStartLogin: (email: string) => Promise<PortalHint>;
  taVerifyOtp: (email: string, otp: string) => Promise<PortalHint>;

  studentStartLogin: (email: string) => Promise<PortalHint>;
  studentVerifyOtp: (email: string, otp: string) => Promise<PortalHint>;

  refreshMe: () => Promise<User | null>;
  logout: () => Promise<void>;
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
    if (!data?.token || !data?.user) {
      throw new Error("Server did not return a session token");
    }

    setSession(data.token as string, data.user as User);
  };

  const studentStartLogin = async (email: string): Promise<PortalHint> => {
    const res = await fetch(`${API_BASE}/auth/student/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ email: email.trim().toLowerCase() }),
    });

    if (!res.ok) throw new Error(await readError(res, "Student login failed"));

    const data = await res.json().catch(() => null);
    return {
      has_admin_access: !!data?.has_admin_access,
      has_ta_access: !!data?.has_ta_access,
      notice: data?.notice || null,
    };
  };

  const studentVerifyOtp = async (email: string, otp: string): Promise<PortalHint> => {
    const res = await fetch(`${API_BASE}/auth/student/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ email: email.trim().toLowerCase(), otp: otp.trim() }),
    });

    if (!res.ok) throw new Error(await readError(res, "Invalid OTP"));

    const data = await res.json().catch(() => null);
    if (!data?.token || !data?.user) {
      throw new Error("Server did not return a session token");
    }

    setSession(data.token as string, data.user as User);

    return {
      has_admin_access: !!data?.has_admin_access,
      has_ta_access: !!data?.has_ta_access,
      notice: data?.notice || null,
    };
  };

  const taStartLogin = async (email: string): Promise<PortalHint> => {
    const res = await fetch(`${API_BASE}/auth/ta/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ email: email.trim().toLowerCase() }),
    });

    if (!res.ok) throw new Error(await readError(res, "TA login failed"));

    const data = await res.json().catch(() => null);
    return {
      has_admin_access: !!data?.has_admin_access,
      notice: data?.notice || null,
    };
  };

  const taVerifyOtp = async (email: string, otp: string): Promise<PortalHint> => {
    const res = await fetch(`${API_BASE}/auth/ta/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ email: email.trim().toLowerCase(), otp: otp.trim() }),
    });

    if (!res.ok) throw new Error(await readError(res, "Invalid OTP"));

    const data = await res.json().catch(() => null);
    if (!data?.token || !data?.user) {
      throw new Error("Server did not return a session token");
    }

    setSession(data.token as string, data.user as User);

    return {
      has_admin_access: !!data?.has_admin_access,
      notice: data?.notice || null,
    };
  };

  const logout = useCallback(async () => {
    try {
      await fetch(`${API_BASE}/auth/admin/logout`, {
        method: "POST",
        credentials: "include",
      });
    } catch {
      // ignore backend logout failure; still clear local session
    } finally {
      clearSession();
    }
  }, [clearSession]);

  useEffect(() => {
    let alive = true;

    (async () => {
      if (!localStorage.getItem(LS_TOKEN)) {
        if (alive) {
          clearSession();
          setAuthReady(true);
        }
        return;
      }

      await refreshMe();

      if (alive) {
        setAuthReady(true);
      }
    })();

    return () => {
      alive = false;
    };
  }, [clearSession, refreshMe]);

  useEffect(() => {
    if (!authReady) return;

    const interval = window.setInterval(() => {
      void refreshMe();
    }, 60000);

    return () => {
      window.clearInterval(interval);
    };
  }, [authReady, refreshMe]);

  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === LS_TOKEN || e.key === LS_USER) {
        const nextToken = localStorage.getItem(LS_TOKEN);
        const nextUserRaw = localStorage.getItem(LS_USER);

        setToken(nextToken);

        if (nextUserRaw) {
          try {
            setUser(JSON.parse(nextUserRaw) as User);
          } catch {
            setUser(null);
          }
        } else {
          setUser(null);
        }
      }
    };

    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

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