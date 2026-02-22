// Website/src/pages/BotPage.tsx
import React, { useEffect, useMemo, useState } from "react";
import { useAuth } from "../services/authService";

const API_BASE =
  (import.meta.env.VITE_AUTH_API_BASE as string | undefined) ||
  (import.meta.env.VITE_CAMERA_API_BASE as string | undefined) ||
  "http://127.0.0.1:9000";

const FRIEND_ML_URL =
  (import.meta.env.VITE_ML_BOT_URL as string | undefined) || "http://127.0.0.1:9000";

function humanBytes(n: number) {
  if (!Number.isFinite(n)) return "-";
  const units = ["B", "KB", "MB", "GB"];
  let i = 0;
  let v = n;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

type Tab = "bot" | "kb";

export default function BotPage() {
  const { token, user } = useAuth();
  const isAdmin = user?.role === "admin";

  const [tab, setTab] = useState<Tab>("bot");

  // ---- KB Sync state (AdminConsole feature) ----
  const [files, setFiles] = useState<FileList | null>(null);
  const [status, setStatus] = useState("");
  const [edgeOnline, setEdgeOnline] = useState(false);
  const [busy, setBusy] = useState<"upload" | "build" | "deploy" | "">("");

  const selected = useMemo(() => {
    if (!files) return [];
    return Array.from(files);
  }, [files]);

  // Poll Jetson/Nano status via YOUR backend
  useEffect(() => {
    const checkStatus = async () => {
      try {
        const res = await fetch(`${API_BASE}/files/edge-status`, {
          headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        });
        if (!res.ok) return setEdgeOnline(false);
        const data = await res.json();
        setEdgeOnline(!!data.online);
      } catch {
        setEdgeOnline(false);
      }
    };

    const t = setInterval(checkStatus, 5000);
    checkStatus();
    return () => clearInterval(t);
  }, [token]);

  const handleUpload = async () => {
    if (!files || files.length === 0) return;
    setBusy("upload");
    setStatus("Uploading documents...");

    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
      formData.append("files", files[i]);
    }

    try {
      const res = await fetch(`${API_BASE}/files/upload`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        body: formData,
      });

      if (res.ok) setStatus("Files uploaded. Ready to build database.");
      else setStatus("Upload failed: " + (await res.text()));
    } catch {
      setStatus("Error connecting to backend.");
    } finally {
      setBusy("");
    }
  };

  const handleBuild = async () => {
    setBusy("build");
    try {
      setStatus("Building Vector Database (this may take a minute)...");
      const res = await fetch(`${API_BASE}/files/build`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });
      if (!res.ok) throw new Error(await res.text());
      setStatus("Build complete.");
    } catch (e: any) {
      setStatus("Error: " + (e?.message || "Build failed"));
    } finally {
      setBusy("");
    }
  };

  const handleDeploy = async () => {
    setBusy("deploy");
    try {
      setStatus("Zipping and deploying to Jetson...");
      const res = await fetch(`${API_BASE}/files/deploy`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });
      if (!res.ok) throw new Error(await res.text());
      setStatus("Deployment complete! Edge is running the latest knowledge base.");
    } catch (e: any) {
      setStatus("Error: " + (e?.message || "Deploy failed"));
    } finally {
      setBusy("");
    }
  };

  // ---- Theme-friendly styles ----
  const shell: React.CSSProperties = {
    width: "100%",
  };

  const container: React.CSSProperties = {
    maxWidth: 1200,
    margin: "0 auto",
  };

  const card: React.CSSProperties = {
    borderRadius: 14,
    border: `1px solid var(--card-border)`,
    background: "var(--card-bg)",
    boxShadow: "var(--shadow)",
    padding: 16,
  };

  const ghostBtn: React.CSSProperties = {
    padding: "10px 14px",
    borderRadius: 12,
    border: `1px solid var(--card-border)`,
    background: "transparent",
    color: "var(--text)",
    cursor: "pointer",
  };

  const primaryBtn: React.CSSProperties = {
    ...ghostBtn,
    background: "rgba(120,150,255,0.14)",
  };

  const disabledBtn: React.CSSProperties = { opacity: 0.55, cursor: "not-allowed" };

  const tabBtn = (active: boolean): React.CSSProperties => ({
    ...ghostBtn,
    background: active ? "rgba(255,255,255,0.06)" : "transparent",
    fontWeight: active ? 800 : 600,
  });

  const pill = (ok: boolean): React.CSSProperties => ({
    padding: "6px 10px",
    borderRadius: 999,
    border: `1px solid var(--card-border)`,
    background: ok ? "rgba(54,211,153,0.10)" : "rgba(255,123,123,0.10)",
    color: ok ? "#36d399" : "#ff7b7b",
    fontWeight: 800,
    fontSize: 12,
    display: "inline-flex",
    alignItems: "center",
    gap: 8,
  });

  return (
    <div style={shell}>
      <div style={container}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
          <div>
            <h2 style={{ margin: 0 }}>Simulator</h2>
            <div style={{ fontSize: 12, opacity: 0.75, marginTop: 4 }}>
              ML UI + Knowledge Base Sync
            </div>
          </div>

          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <button style={tabBtn(tab === "bot")} onClick={() => setTab("bot")}>
              ML Bot
            </button>
            <button style={tabBtn(tab === "kb")} onClick={() => setTab("kb")}>
              KB Sync
            </button>

            <a
              href={FRIEND_ML_URL}
              target="_blank"
              rel="noreferrer"
              style={{
                ...ghostBtn,
                textDecoration: "none",
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
              }}
              title="Open ML UI in a new tab"
            >
              Open →{/* new tab */}
            </a>
          </div>
        </div>

        {tab === "bot" && (
          <div style={{ marginTop: 14, ...card, padding: 0, overflow: "hidden" }}>
            <iframe
              title="ML Bot"
              src={FRIEND_ML_URL}
              style={{ width: "100%", height: "78vh", border: "none", background: "transparent" }}
            />
          </div>
        )}

        {tab === "kb" && (
          <div style={{ marginTop: 14, ...card }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
              <div>
                <div style={{ fontSize: 16, fontWeight: 900 }}>Knowledge Base Sync</div>
                <div style={{ fontSize: 12, opacity: 0.75, marginTop: 4 }}>
                  Upload → Build vector DB → Deploy to Jetson Nano
                </div>
              </div>

              <div style={pill(edgeOnline)}>
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: 99,
                    background: edgeOnline ? "#36d399" : "#ff7b7b",
                    boxShadow: edgeOnline ? "0 0 10px rgba(54,211,153,0.35)" : "0 0 10px rgba(255,123,123,0.35)",
                  }}
                />
                {edgeOnline ? "EDGE ONLINE" : "EDGE OFFLINE"}
              </div>
            </div>

            {!isAdmin && (
              <div style={{ marginTop: 12, padding: 12, borderRadius: 12, border: `1px solid var(--card-border)` }}>
                <div style={{ fontWeight: 800, marginBottom: 6 }}>Admin only</div>
                <div style={{ fontSize: 12, opacity: 0.8 }}>
                  You’re logged in as <b>{user?.email || "unknown"}</b>. KB sync actions require admin.
                </div>
              </div>
            )}

            <div style={{ marginTop: 14, display: "flex", gap: 16, flexWrap: "wrap" }}>
              <div style={{ flex: "1 1 520px" }}>
                <div style={{ fontSize: 12, opacity: 0.75, marginBottom: 8 }}>Select documents</div>

                <label
                  style={{
                    display: "block",
                    padding: 14,
                    borderRadius: 12,
                    border: `1px dashed var(--card-border)`,
                    background: "rgba(0,0,0,0.12)",
                    cursor: "pointer",
                  }}
                >
                  <input
                    type="file"
                    multiple
                    onChange={(e) => setFiles(e.target.files)}
                    style={{ display: "none" }}
                  />
                  <div style={{ fontWeight: 800, marginBottom: 6 }}>
                    {selected.length ? `${selected.length} file(s) selected` : "Click to choose files"}
                  </div>
                  <div style={{ fontSize: 12, opacity: 0.75 }}>PDF/TXT recommended.</div>
                </label>

                {selected.length > 0 && (
                  <div
                    style={{
                      marginTop: 12,
                      borderRadius: 12,
                      border: `1px solid var(--card-border)`,
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        padding: 10,
                        fontSize: 12,
                        opacity: 0.75,
                        borderBottom: `1px solid var(--card-border)`,
                      }}
                    >
                      Selected
                    </div>

                    <div style={{ maxHeight: 200, overflow: "auto" }}>
                      {selected.map((f) => (
                        <div
                          key={f.name + f.size}
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            gap: 12,
                            padding: "10px 12px",
                            borderTop: `1px solid var(--card-border)`,
                          }}
                        >
                          <div style={{ minWidth: 0 }}>
                            <div
                              style={{
                                fontSize: 13,
                                whiteSpace: "nowrap",
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                              }}
                            >
                              {f.name}
                            </div>
                            <div style={{ fontSize: 12, opacity: 0.7 }}>{humanBytes(f.size)}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <div style={{ width: 300 }}>
                <div style={{ fontSize: 12, opacity: 0.75, marginBottom: 8 }}>Actions</div>

                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  <button
                    onClick={handleUpload}
                    disabled={!isAdmin || busy !== "" || selected.length === 0}
                    style={{
                      ...primaryBtn,
                      ...((!isAdmin || busy !== "" || selected.length === 0) ? disabledBtn : {}),
                    }}
                  >
                    {busy === "upload" ? "Uploading…" : "1) Stage / Upload"}
                  </button>

                  <button
                    onClick={handleBuild}
                    disabled={!isAdmin || busy !== ""}
                    style={{ ...ghostBtn, ...((!isAdmin || busy !== "") ? disabledBtn : {}) }}
                  >
                    {busy === "build" ? "Building…" : "2) Build Vector DB"}
                  </button>

                  <button
                    onClick={handleDeploy}
                    disabled={!isAdmin || busy !== "" || !edgeOnline}
                    style={{
                      ...ghostBtn,
                      ...((!isAdmin || busy !== "" || !edgeOnline) ? disabledBtn : {}),
                    }}
                    title={!edgeOnline ? "Edge must be online to deploy" : ""}
                  >
                    {busy === "deploy" ? "Deploying…" : "3) Deploy to Edge"}
                  </button>

                  <div style={{ fontSize: 12, opacity: 0.7, marginTop: 6 }}>
                    Edge status comes from <span style={{ fontFamily: "monospace" }}>/files/edge-status</span>.
                  </div>
                </div>
              </div>
            </div>

            <div
              style={{
                marginTop: 14,
                padding: 12,
                borderRadius: 12,
                border: `1px solid var(--card-border)`,
                background: "rgba(0,0,0,0.12)",
                fontFamily: "monospace",
                fontSize: 13,
                opacity: 0.92,
              }}
            >
              {status ? `> ${status}` : "> System idle. Awaiting documents..."}
            </div>
          </div>
        )}

        <div style={{ marginTop: 10, fontSize: 12, opacity: 0.75 }}>
          Using API: <span style={{ fontFamily: "monospace" }}>{API_BASE}</span>
        </div>
      </div>
    </div>
  );
}