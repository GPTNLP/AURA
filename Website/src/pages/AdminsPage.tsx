import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../services/authService";

type AdminRow = { email: string };

type ListAdminsResponse = {
  admins: AdminRow[];
};

function isEmail(s: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s.trim());
}

export default function AdminsPage() {
  const { token, user } = useAuth();

  const API_BASE =
    (import.meta.env.VITE_AUTH_API_BASE as string | undefined)?.trim() ||
    (import.meta.env.VITE_API_URL as string | undefined)?.trim() ||
    "http://127.0.0.1:9000";

  const isAdmin = (user?.role || "").toLowerCase() === "admin";

  const authHeaders = useMemo(() => {
    const h = new Headers();
    if (token) h.set("Authorization", `Bearer ${token}`);
    h.set("Content-Type", "application/json");
    return h;
  }, [token]);

  const [admins, setAdmins] = useState<AdminRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string>("");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  async function readErr(res: Response, fallback: string) {
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

  async function refresh() {
    if (!token) return;
    setErr("");
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/auth/admin/admins`, {
        method: "GET",
        headers: authHeaders,
        credentials: "include",
      });
      if (!res.ok) throw new Error(await readErr(res, `Failed (${res.status})`));
      const data = (await res.json()) as ListAdminsResponse;
      setAdmins(Array.isArray(data?.admins) ? data.admins : []);
    } catch (e: any) {
      setErr(e?.message || "Failed to load admins");
    } finally {
      setLoading(false);
    }
  }

  async function addAdmin() {
    const e = email.trim().toLowerCase();
    const p = password;

    setErr("");
    if (!isEmail(e)) {
      setErr("Enter a valid email.");
      return;
    }
    if (!p || p.length < 8) {
      setErr("Password must be at least 8 characters.");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/auth/admin/admins`, {
        method: "POST",
        headers: authHeaders,
        credentials: "include",
        body: JSON.stringify({ email: e, password: p }),
      });
      if (!res.ok) throw new Error(await readErr(res, `Failed (${res.status})`));

      setEmail("");
      setPassword("");
      await refresh();
    } catch (e: any) {
      setErr(e?.message || "Failed to add admin");
    } finally {
      setLoading(false);
    }
  }

  async function removeAdmin(targetEmail: string) {
    setErr("");
    const ok = confirm(`Remove admin: ${targetEmail}?`);
    if (!ok) return;

    setLoading(true);
    try {
      const res = await fetch(
        `${API_BASE}/auth/admin/admins/${encodeURIComponent(targetEmail)}`,
        {
          method: "DELETE",
          headers: authHeaders,
          credentials: "include",
        }
      );
      if (!res.ok) throw new Error(await readErr(res, `Failed (${res.status})`));
      await refresh();
    } catch (e: any) {
      setErr(e?.message || "Failed to remove admin");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (token && isAdmin) void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, isAdmin]);

  // Hard gates (router also protects it, but this makes UX nicer)
  if (!token) {
    return (
      <div style={{ padding: 18 }}>
        <h2 style={{ margin: 0 }}>Admins</h2>
        <p style={{ opacity: 0.8 }}>You must be logged in.</p>
      </div>
    );
  }

  if (!isAdmin) {
    return (
      <div style={{ padding: 18 }}>
        <h2 style={{ margin: 0 }}>Admins</h2>
        <p style={{ opacity: 0.8 }}>Forbidden (admin only).</p>
      </div>
    );
  }

  return (
    <div style={{ padding: 18, maxWidth: 980, margin: "0 auto" }}>
      <div
        style={{
          background: "var(--card-bg)",
          border: "1px solid var(--card-border)",
          borderRadius: "var(--card-radius)",
          boxShadow: "var(--shadow)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            padding: 16,
            borderBottom: "1px solid var(--card-border)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
          }}
        >
          <div>
            <h2 style={{ margin: 0, fontWeight: 900 }}>Admin Management</h2>
            <div style={{ fontSize: 12, opacity: 0.8, marginTop: 4 }}>
              Add / remove admins (admin-only)
            </div>
          </div>

          <button
            onClick={refresh}
            disabled={loading}
            style={{
              padding: "10px 12px",
              borderRadius: 12,
              border: "1px solid var(--card-border)",
              background: "var(--card-bg)",
              fontWeight: 900,
              cursor: loading ? "not-allowed" : "pointer",
              opacity: loading ? 0.7 : 1,
            }}
          >
            Refresh
          </button>
        </div>

        {err && (
          <div
            style={{
              margin: 16,
              padding: 12,
              borderRadius: 12,
              border: "1px solid color-mix(in srgb, var(--status-bad) 35%, var(--card-border))",
              background: "color-mix(in srgb, var(--status-bad) 10%, var(--card-bg))",
              color: "color-mix(in srgb, var(--status-bad) 85%, var(--text))",
              fontWeight: 700,
            }}
          >
            {err}
          </div>
        )}

        <div style={{ padding: 16, display: "grid", gap: 16 }}>
          {/* Add admin */}
          <div
            style={{
              border: "1px solid var(--card-border)",
              borderRadius: 16,
              padding: 14,
              background: "color-mix(in srgb, var(--card-bg) 90%, var(--accent-soft))",
            }}
          >
            <div style={{ fontWeight: 900, marginBottom: 10 }}>Add Admin</div>

            <div style={{ display: "grid", gap: 10, gridTemplateColumns: "1fr 1fr auto" }}>
              <input
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="email@domain.com"
                style={{
                  padding: "12px 12px",
                  borderRadius: 12,
                  border: "1px solid var(--card-border)",
                  background: "var(--card-bg)",
                  color: "var(--text)",
                  outline: "none",
                }}
              />

              <input
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="password (min 8 chars)"
                type="password"
                style={{
                  padding: "12px 12px",
                  borderRadius: 12,
                  border: "1px solid var(--card-border)",
                  background: "var(--card-bg)",
                  color: "var(--text)",
                  outline: "none",
                }}
              />

              <button
                onClick={addAdmin}
                disabled={loading}
                style={{
                  padding: "12px 16px",
                  borderRadius: 12,
                  border: "1px solid rgba(0,0,0,0)",
                  background: "var(--accent)",
                  color: "white",
                  fontWeight: 900,
                  cursor: loading ? "not-allowed" : "pointer",
                  opacity: loading ? 0.7 : 1,
                }}
              >
                Add
              </button>
            </div>

            <div style={{ fontSize: 12, opacity: 0.75, marginTop: 8 }}>
              This calls: <span style={{ fontFamily: "monospace" }}>/auth/admin/admins</span>
            </div>
          </div>

          {/* Admin list */}
          <div
            style={{
              border: "1px solid var(--card-border)",
              borderRadius: 16,
              padding: 14,
            }}
          >
            <div style={{ fontWeight: 900, marginBottom: 10 }}>
              Current Admins ({admins.length})
            </div>

            {admins.length === 0 ? (
              <div style={{ opacity: 0.75 }}>No admins found.</div>
            ) : (
              <div style={{ display: "grid", gap: 10 }}>
                {admins.map((a) => (
                  <div
                    key={a.email}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: 12,
                      padding: "12px 12px",
                      borderRadius: 12,
                      border: "1px solid var(--card-border)",
                      background: "var(--card-bg)",
                    }}
                  >
                    <div style={{ fontFamily: "ui-monospace, Menlo, Monaco, Consolas, monospace" }}>
                      {a.email}
                    </div>

                    <button
                      onClick={() => removeAdmin(a.email)}
                      disabled={loading}
                      style={{
                        padding: "10px 12px",
                        borderRadius: 12,
                        border: "1px solid var(--card-border)",
                        background: "color-mix(in srgb, var(--status-bad) 10%, var(--card-bg))",
                        fontWeight: 900,
                        cursor: loading ? "not-allowed" : "pointer",
                        opacity: loading ? 0.7 : 1,
                      }}
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            )}

            <div style={{ fontSize: 12, opacity: 0.75, marginTop: 10 }}>
              Backend should block removing yourself (recommended).
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}