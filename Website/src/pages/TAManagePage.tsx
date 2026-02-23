import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../services/authService";

type TaRow = {
  email: string;
  added_by?: string;
  added_ts?: number;
};

const API_BASE =
  (import.meta.env.VITE_AUTH_API_BASE as string | undefined) ||
  (import.meta.env.VITE_CAMERA_API_BASE as string | undefined) ||
  "http://127.0.0.1:9000";

async function readErr(res: Response) {
  try {
    const j = await res.json();
    return j?.detail || j?.message || (await res.text());
  } catch {
    try {
      return (await res.text()) || `Request failed (${res.status})`;
    } catch {
      return `Request failed (${res.status})`;
    }
  }
}

export default function TAManagePage() {
  const { token } = useAuth();
  const [items, setItems] = useState<TaRow[]>([]);
  const [email, setEmail] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const headers = useMemo(() => {
    return {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };
  }, [token]);

  const load = async () => {
    if (!token) return;
    setErr(null);

    const res = await fetch(`${API_BASE}/admin/ta/list`, { headers });
    if (!res.ok) {
      setErr(await readErr(res));
      setItems([]);
      return;
    }

    const data = await res.json().catch(() => null);
    setItems(Array.isArray(data?.items) ? data.items : []);
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const addTa = async () => {
    if (!token) return;
    setErr(null);
    setLoading(true);

    try {
      const e = email.trim().toLowerCase();
      if (!e) throw new Error("Enter an email");

      const res = await fetch(`${API_BASE}/admin/ta/add`, {
        method: "POST",
        headers,
        body: JSON.stringify({ email: e }),
      });

      if (!res.ok) throw new Error(await readErr(res));

      setEmail("");
      const data = await res.json().catch(() => null);
      setItems(Array.isArray(data?.items) ? data.items : []);
    } catch (ex: any) {
      setErr(ex?.message || "Failed to add TA");
    } finally {
      setLoading(false);
    }
  };

  const removeTa = async (taEmail: string) => {
    if (!token) return;
    setErr(null);
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/admin/ta/remove`, {
        method: "POST",
        headers,
        body: JSON.stringify({ email: taEmail }),
      });

      if (!res.ok) throw new Error(await readErr(res));

      const data = await res.json().catch(() => null);
      setItems(Array.isArray(data?.items) ? data.items : []);
    } catch (ex: any) {
      setErr(ex?.message || "Failed to remove TA");
    } finally {
      setLoading(false);
    }
  };

  const fmt = (ts?: number) => {
    if (!ts) return "";
    try {
      return new Date(ts * 1000).toLocaleString();
    } catch {
      return "";
    }
  };

  if (!token) {
    return (
      <div style={{ padding: 16 }}>
        <h2 style={{ margin: 0 }}>TA Manager</h2>
        <p style={{ marginTop: 6, opacity: 0.8 }}>Please login as an admin.</p>
      </div>
    );
  }

  return (
    <div style={{ padding: 16 }}>
      <h2 style={{ margin: 0 }}>TA Manager</h2>
      <p style={{ marginTop: 6, opacity: 0.8 }}>
        Add/remove TA access by email. TAs can upload to the database, but can only delete/move files they uploaded.
      </p>

      <div style={{ display: "flex", gap: 10, marginTop: 14, maxWidth: 520 }}>
        <input
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="someone@tamu.edu"
          style={{ flex: 1, padding: 10, borderRadius: 10, border: "1px solid rgba(0,0,0,0.15)" }}
        />
        <button onClick={addTa} disabled={loading} style={{ padding: "10px 14px", borderRadius: 10 }}>
          {loading ? "..." : "Add"}
        </button>
      </div>

      {err && (
        <div style={{ marginTop: 12, color: "#b00020", fontWeight: 600 }}>
          {err}
        </div>
      )}

      <div style={{ marginTop: 18 }}>
        <div style={{ fontWeight: 700, marginBottom: 8 }}>Current TAs</div>
        <div style={{ border: "1px solid rgba(0,0,0,0.12)", borderRadius: 12, overflow: "hidden" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead style={{ background: "rgba(0,0,0,0.04)" }}>
              <tr>
                <th style={{ textAlign: "left", padding: 10 }}>Email</th>
                <th style={{ textAlign: "left", padding: 10 }}>Added By</th>
                <th style={{ textAlign: "left", padding: 10 }}>Added</th>
                <th style={{ padding: 10 }} />
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={4} style={{ padding: 12, opacity: 0.7 }}>
                    No TAs yet.
                  </td>
                </tr>
              ) : (
                items.map((it) => (
                  <tr key={it.email} style={{ borderTop: "1px solid rgba(0,0,0,0.08)" }}>
                    <td style={{ padding: 10 }}>{it.email}</td>
                    <td style={{ padding: 10, opacity: 0.8 }}>{it.added_by || ""}</td>
                    <td style={{ padding: 10, opacity: 0.8 }}>{fmt(it.added_ts)}</td>
                    <td style={{ padding: 10, textAlign: "right" }}>
                      <button
                        onClick={() => removeTa(it.email)}
                        disabled={loading}
                        style={{ padding: "8px 10px", borderRadius: 10 }}
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}