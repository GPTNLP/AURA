import { createContext, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";

interface User {
  email: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType>(null as any);

const LS_USER = "arua-user";
const LS_TOKEN = "arua-auth-token";

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

  const login = async (email: string, password: string) => {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: email.trim(), password }),
    });

    if (!res.ok) {
      const msg = await res.text();
      throw new Error(msg || "Login failed");
    }

    const data = await res.json();
    const t = data.token as string;
    const u = data.user as User;

    setToken(t);
    setUser(u);

    localStorage.setItem(LS_TOKEN, t);
    localStorage.setItem(LS_USER, JSON.stringify(u));
  };

  const logout = () => {
    setUser(null);
    setToken(null);
    localStorage.removeItem(LS_USER);
    localStorage.removeItem(LS_TOKEN);
  };

  const value = useMemo(() => ({ user, token, login, logout }), [user, token]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
