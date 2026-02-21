import React, { useEffect, useMemo, useState } from "react";
import { useAuth } from "../services/authService";

const API_BASE =
  (import.meta.env.VITE_AUTH_API_BASE as string | undefined) ||
  "http://127.0.0.1:9000";

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

export default function FilesPage() {
  const { token, user } = useAuth();
  const isAdmin = user?.role === "admin";

  const [files, setFiles] = useState<FileList | null>(null);
  const [status, setStatus] = useState("");
  const [edgeOnline, setEdgeOnline] = useState(false);
  const [busy, setBusy] = useState<"upload" | "build" | "deploy" | "">("");

  const selected = useMemo(() => {
    if (!files) return [];
    return Array.from(files);
  }, [files]);

  useEffect(() => {
    const checkStatus = async () => {
      try {
        const res = await fetch(`${API_BASE}/files/edge-status`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (!res.ok) return setEdgeOnline(false);
        const data = await res.json();
        setEdgeOnline(!!data.online);
      } catch {
        setEdgeOnline(false);
      }
    };

    const timer = setInterval(checkStatus, 5000);
    checkStatus();
    return () => clearInterval(timer);
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
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      });

      if (res.ok) {
        setStatus("Upload complete. Ready to build.");
      } else {
        const text = await res.text();
        setStatus(`Upload failed: ${text}`);
      }
    } catch {
      setStatus("Error connecting to backend.");
    } finally {
      setBusy("");
    }
  };

  const handleBuild = async () => {
    setBusy("build");
    try {
      setStatus("Building Vector DB (this may take a minute)...");
      const res = await fetch(`${API_BASE}/files/build`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error(await res.text());
      setStatus("Build complete.");
    } catch (err: any) {
      setStatus("Error: " + (err?.message || "Build failed"));
    } finally {
      setBusy("");
    }
  };

  const handleDeploy = async () => {
    setBusy("deploy");
    try {
      setStatus("Deploying to Edge device...");
      const res = await fetch(`${API_BASE}/files/deploy`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error(await res.text());
      setStatus("Deployment complete!");
    } catch (err: any) {
      setStatus("Error: " + (err?.message || "Deploy failed"));
    } finally {
      setBusy("");
    }
  };

  const cardStyle: React.CSSProperties = {
    padding: 18,
    borderRadius: 14,
    border: "1px solid rgba(120,150,255,0.18)",
    background: "rgba(255,255,255,0.04)",
  };

  const btn = (variant: "primary" | "ghost" | "danger" = "ghost"): React.CSSProperties => ({
    padding: "10px 14px",
    borderRadius: 10,
    border:
      variant === "primary"
        ? "1px solid rgba(120,150,255,0.35)"
        : variant === "danger"
        ? "1px solid rgba(255,120,120,0.25)"
        : "1px solid rgba(120,150,255,0.18)",
    background:
      variant === "primary"
        ? "rgba(120,150,255,0.14)"
        : variant === "danger"
        ? "rgba(255,120,120,0.10)"
        : "transparent",
    color: "var(--text)",
    cursor: "pointer",
  });

  const disabledBtn: React.CSSProperties = { opacity: 0.55, cursor: "not-allowed" };

  return (
    <div style={{ width: "100%" }}>
      <div style={{ maxWidth: 980, margin: "0 auto" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
          <div>
            <h2 style={{ margin: 0 }}>Files</h2>
            <div style={{ fontSize: 12, opacity: 0.75, marginTop: 4 }}>
              Upload docs → build vector DB → deploy to Jetson
            </div>
          </div>

          <div style={{ fontSize: 12, opacity: 0.9 }}>
            Edge:{" "}
            <span
              style={{
                padding: "6px 10px",
                borderRadius: 999,
                border: "1px solid rgba(120,150,255,0.18)",
                background: edgeOnline ? "rgba(54,211,153,0.10)" : "rgba(255,123,123,0.10)",
                color: edgeOnline ? "#36d399" : "#ff7b7b",
                fontWeight: 700,
              }}
            >
              {edgeOnline ? "ONLINE" : "OFFLINE"}
            </span>
          </div>
        </div>

        <div style={cardStyle}>
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "flex-start" }}>
            <div style={{ flex: "1 1 420px" }}>
              <div style={{ fontSize: 12, opacity: 0.75, marginBottom: 8 }}>Select documents</div>

              <label
                style={{
                  display: "block",
                  padding: 14,
                  borderRadius: 12,
                  border: "1px dashed rgba(120,150,255,0.25)",
                  background: "rgba(0,0,0,0.18)",
                  cursor: "pointer",
                }}
              >
                <input
                  type="file"
                  multiple
                  onChange={(e) => setFiles(e.target.files)}
                  style={{ display: "none" }}
                />
                <div style={{ fontWeight: 700, marginBottom: 6 }}>
                  {selected.length ? `${selected.length} file(s) selected` : "Click to choose files"}
                </div>
                <div style={{ fontSize: 12, opacity: 0.75 }}>
                  PDFs and text files work best for indexing.
                </div>
              </label>

              {selected.length > 0 && (
                <div style={{ marginTop: 12, borderRadius: 12, border: "1px solid rgba(120,150,255,0.12)" }}>
                  <div style={{ padding: 10, fontSize: 12, opacity: 0.75, borderBottom: "1px solid rgba(120,150,255,0.10)" }}>
                    Selected
                  </div>
                  <div style={{ maxHeight: 180, overflow: "auto" }}>
                    {selected.map((f) => (
                      <div
                        key={f.name + f.size}
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          gap: 10,
                          padding: "10px 12px",
                          borderTop: "1px solid rgba(120,150,255,0.08)",
                        }}
                      >
                        <div style={{ minWidth: 0 }}>
                          <div style={{ fontSize: 13, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
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

            <div style={{ flex: "0 0 280px" }}>
              <div style={{ fontSize: 12, opacity: 0.75, marginBottom: 8 }}>Actions</div>

              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <button
                  onClick={handleUpload}
                  style={{ ...btn("primary"), ...(busy ? disabledBtn : {}) }}
                  disabled={busy !== "" || selected.length === 0}
                >
                  {busy === "upload" ? "Uploading…" : "1) Upload"}
                </button>

                <button
                  onClick={handleBuild}
                  style={{ ...btn("ghost"), ...(busy ? disabledBtn : {}) }}
                  disabled={busy !== ""}
                >
                  {busy === "build" ? "Building…" : "2) Build"}
                </button>

                <button
                  onClick={handleDeploy}
                  style={{
                    ...btn("ghost"),
                    ...(busy ? disabledBtn : {}),
                    ...(!edgeOnline ? disabledBtn : {}),
                  }}
                  disabled={busy !== "" || !edgeOnline}
                  title={!edgeOnline ? "Edge device must be online" : ""}
                >
                  {busy === "deploy" ? "Deploying…" : "3) Deploy"}
                </button>

                {!isAdmin && (
                  <div style={{ fontSize: 12, opacity: 0.75, marginTop: 6 }}>
                    Note: Admins can also delete/mkdir once we expose the UI.
                  </div>
                )}
              </div>
            </div>
          </div>

          <div
            style={{
              marginTop: 14,
              padding: 12,
              borderRadius: 12,
              border: "1px solid rgba(120,150,255,0.12)",
              background: "rgba(0,0,0,0.20)",
              fontFamily: "monospace",
              fontSize: 13,
              opacity: 0.92,
            }}
          >
            {status ? `> ${status}` : "> Idle"}
          </div>
        </div>
      </div>
    </div>
  );
}