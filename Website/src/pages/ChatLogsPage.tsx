// Website/src/pages/ChatLogsPage.tsx
import React, { useEffect, useMemo, useState } from "react";
import { useAuth } from "../services/authService";

type LogItem = {
  ts: number;
  event?: string;
  user_email?: string;
  user_role?: string;
  prompt?: string;
  response_preview?: string;
  model?: string;
  latency_ms?: number;
  meta?: Record<string, any>;
};

const API_BASE =
  (import.meta.env.VITE_AUTH_API_BASE as string | undefined) ||
  (import.meta.env.VITE_CAMERA_API_BASE as string | undefined) ||
  "http://127.0.0.1:9000";

function fmtTime(ts: number) {
  try {
    return new Date(ts * 1000).toLocaleString();
  } catch {
    return String(ts);
  }
}

const inputStyle: React.CSSProperties = {
  padding: "10px 12px",
  borderRadius: 10,
  border: "1px solid rgba(120,150,255,0.18)",
  background: "rgba(6,12,22,0.65)",
  color: "var(--text)",
  outline: "none",
};

const selectStyle: React.CSSProperties = {
  ...inputStyle,
  cursor: "pointer",
  colorScheme: "dark",
};

export default function ChatLogsPage() {
  const { token, user } = useAuth();
  const isAdmin = user?.role === "admin";

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [items, setItems] = useState<LogItem[]>([]);
  const [matched, setMatched] = useState<number>(0);

  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const [event, setEvent] = useState("");

  const [limit, setLimit] = useState(200);
  const [offset, setOffset] = useState(0);

  const canFetch = !!token && isAdmin;

  const queryString = useMemo(() => {
    const p = new URLSearchParams();
    p.set("limit", String(limit));
    p.set("offset", String(offset));
    if (q.trim()) p.set("q", q.trim());
    if (role) p.set("role", role);
    if (event) p.set("event", event);
    return p.toString();
  }, [limit, offset, q, role, event]);

  const fetchLogs = async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/logs/list?${queryString}`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!res.ok) {
        const txt = await res.text();
        throw new Error(txt || `Request failed (${res.status})`);
      }

      const data = await res.json();
      setItems((data.items || []) as LogItem[]);
      setMatched(Number(data.total_matched || 0));
    } catch (e: any) {
      setError(e?.message || "Failed to load logs");
      setItems([]);
      setMatched(0);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!canFetch) return;
    fetchLogs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canFetch, queryString]);

  if (!token) {
    return (
      <div style={{ maxWidth: 900, margin: "0 auto" }}>
        <h2 style={{ marginTop: 0 }}>Chat Logs</h2>
        <div style={{ opacity: 0.8 }}>Please login.</div>
      </div>
    );
  }

  if (!isAdmin) {
    return (
      <div style={{ maxWidth: 900, margin: "0 auto" }}>
        <h2 style={{ marginTop: 0 }}>Chat Logs</h2>
        <div style={{ opacity: 0.8 }}>Admin only.</div>
      </div>
    );
  }

  return (
    <div style={{ width: "100%" }}>
      <div style={{ maxWidth: 1200, margin: "0 auto" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
          <h2 style={{ marginTop: 0 }}>Chat Logs</h2>

          <button
            onClick={fetchLogs}
            disabled={loading}
            style={{
              padding: "10px 14px",
              borderRadius: 10,
              border: "1px solid rgba(120,150,255,0.22)",
              background: "rgba(255,255,255,0.04)",
              color: "var(--text)",
              cursor: "pointer",
            }}
          >
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>

        <div
          style={{
            padding: 14,
            borderRadius: 12,
            border: "1px solid rgba(120,150,255,0.18)",
            background: "rgba(255,255,255,0.04)",
            marginBottom: 14,
          }}
        >
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
            <input
              value={q}
              onChange={(e) => {
                setOffset(0);
                setQ(e.target.value);
              }}
              placeholder="Search (email / prompt / meta...)"
              style={{ ...inputStyle, flex: "1 1 320px" }}
            />

            <select
              value={role}
              onChange={(e) => {
                setOffset(0);
                setRole(e.target.value);
              }}
              style={selectStyle}
            >
              <option value="">All Roles</option>
              <option value="admin">Admin</option>
              <option value="student">Student</option>
            </select>

            <select
              value={event}
              onChange={(e) => {
                setOffset(0);
                setEvent(e.target.value);
              }}
              style={selectStyle}
            >
              <option value="">All Events</option>
              <option value="chat">chat</option>
              <option value="bot">bot</option>
              <option value="upload">upload</option>
              <option value="login">login</option>
            </select>

            <select
              value={String(limit)}
              onChange={(e) => {
                setOffset(0);
                setLimit(parseInt(e.target.value, 10));
              }}
              style={selectStyle}
            >
              <option value="50">50</option>
              <option value="100">100</option>
              <option value="200">200</option>
              <option value="500">500</option>
            </select>

            <button
              onClick={fetchLogs}
              disabled={loading}
              style={{
                padding: "10px 14px",
                borderRadius: 10,
                border: "1px solid rgba(120,150,255,0.22)",
                background: "rgba(255,255,255,0.04)",
                color: "var(--text)",
                cursor: "pointer",
              }}
            >
              Search
            </button>

            <button
              onClick={() => {
                setQ("");
                setRole("");
                setEvent("");
                setOffset(0);
              }}
              disabled={loading}
              style={{
                padding: "10px 14px",
                borderRadius: 10,
                border: "1px solid rgba(120,150,255,0.12)",
                background: "transparent",
                color: "var(--text)",
                cursor: "pointer",
                opacity: 0.85,
              }}
            >
              Clear
            </button>
          </div>

          <div style={{ marginTop: 10, fontSize: 12, opacity: 0.8 }}>
            Matched: <b>{matched}</b>
          </div>

          {error && (
            <div style={{ marginTop: 10, color: "#ff7b7b", fontSize: 13, whiteSpace: "pre-wrap" }}>
              {error}
            </div>
          )}
        </div>

        <div
          style={{
            borderRadius: 12,
            border: "1px solid rgba(120,150,255,0.18)",
            overflow: "hidden",
            background: "rgba(0,0,0,0.20)",
          }}
        >
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ textAlign: "left", background: "rgba(255,255,255,0.04)" }}>
                  <th style={{ padding: 10, borderBottom: "1px solid rgba(120,150,255,0.12)" }}>Time</th>
                  <th style={{ padding: 10, borderBottom: "1px solid rgba(120,150,255,0.12)" }}>User</th>
                  <th style={{ padding: 10, borderBottom: "1px solid rgba(120,150,255,0.12)" }}>Role</th>
                  <th style={{ padding: 10, borderBottom: "1px solid rgba(120,150,255,0.12)" }}>Event</th>
                  <th style={{ padding: 10, borderBottom: "1px solid rgba(120,150,255,0.12)" }}>Prompt</th>
                  <th style={{ padding: 10, borderBottom: "1px solid rgba(120,150,255,0.12)" }}>Latency</th>
                </tr>
              </thead>
              <tbody>
                {items.length === 0 && !loading && (
                  <tr>
                    <td colSpan={6} style={{ padding: 14, opacity: 0.75 }}>
                      No logs found.
                    </td>
                  </tr>
                )}

                {items.map((it, idx) => (
                  <tr key={idx} style={{ borderTop: "1px solid rgba(120,150,255,0.08)" }}>
                    <td style={{ padding: 10, whiteSpace: "nowrap", opacity: 0.9 }}>{fmtTime(it.ts)}</td>
                    <td style={{ padding: 10, whiteSpace: "nowrap" }}>{it.user_email || "-"}</td>
                    <td style={{ padding: 10, whiteSpace: "nowrap" }}>{it.user_role || "-"}</td>
                    <td style={{ padding: 10, whiteSpace: "nowrap" }}>{it.event || "-"}</td>
                    <td style={{ padding: 10, minWidth: 420 }}>
                      <div style={{ whiteSpace: "pre-wrap", opacity: 0.95 }}>
                        {it.prompt ? it.prompt.slice(0, 500) : "-"}
                        {it.prompt && it.prompt.length > 500 ? "…" : ""}
                      </div>
                    </td>
                    <td style={{ padding: 10, whiteSpace: "nowrap" }}>
                      {typeof it.latency_ms === "number" ? `${it.latency_ms}ms` : "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              padding: 12,
              borderTop: "1px solid rgba(120,150,255,0.12)",
              background: "rgba(255,255,255,0.02)",
            }}
          >
            <div style={{ fontSize: 12, opacity: 0.8 }}>
              Showing {items.length} / {matched} (offset {offset})
            </div>

            <div style={{ display: "flex", gap: 10 }}>
              <button
                onClick={() => setOffset((v) => Math.max(0, v - limit))}
                disabled={loading || offset === 0}
                style={{
                  padding: "10px 14px",
                  borderRadius: 10,
                  border: "1px solid rgba(120,150,255,0.18)",
                  background: "transparent",
                  color: "var(--text)",
                  cursor: "pointer",
                  opacity: offset === 0 ? 0.5 : 1,
                }}
              >
                ← Prev
              </button>

              <button
                onClick={() => setOffset((v) => v + limit)}
                disabled={loading || offset + limit >= matched}
                style={{
                  padding: "10px 14px",
                  borderRadius: 10,
                  border: "1px solid rgba(120,150,255,0.18)",
                  background: "transparent",
                  color: "var(--text)",
                  cursor: "pointer",
                  opacity: offset + limit >= matched ? 0.5 : 1,
                }}
              >
                Next →
              </button>
            </div>
          </div>
        </div>

        <div style={{ marginTop: 10, fontSize: 12, opacity: 0.75 }}>
          Endpoint: <span style={{ fontFamily: "monospace" }}>{API_BASE}/logs/list</span>
        </div>
      </div>
    </div>
  );
}