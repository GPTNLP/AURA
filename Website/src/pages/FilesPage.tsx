import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../services/authService";
import "../styles/page-ui.css";

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

  const selected = useMemo(() => (files ? Array.from(files) : []), [files]);

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
    for (let i = 0; i < files.length; i++) formData.append("files", files[i]);

    try {
      const res = await fetch(`${API_BASE}/files/upload`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      });

      if (res.ok) setStatus("Upload complete. Ready to build.");
      else setStatus(`Upload failed: ${await res.text()}`);
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

  return (
    <div className="page-shell">
      <div className="page-wrap">
        <div className="page-header">
          <div>
            <h2 className="page-title">Files</h2>
            <div className="page-subtitle">Upload docs → build vector DB → deploy to Jetson</div>
          </div>

          <div className="badge" title="Edge device availability">
            Edge:
            <span
              style={{
                marginLeft: 6,
                padding: "4px 10px",
                borderRadius: 999,
                border: "1px solid var(--card-border)",
                background: edgeOnline ? "color-mix(in srgb, var(--status-good) 12%, var(--card-bg))"
                                      : "color-mix(in srgb, var(--status-bad) 12%, var(--card-bg))",
                color: edgeOnline ? "var(--status-good)" : "var(--status-bad)",
                fontWeight: 900,
              }}
            >
              {edgeOnline ? "ONLINE" : "OFFLINE"}
            </span>
          </div>
        </div>

        <div className="card card-pad">
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "flex-start" }}>
            <div style={{ flex: "1 1 520px" }}>
              <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>
                Select documents
              </div>

              <label className="panel" style={{ display: "block", cursor: "pointer" }}>
                <input
                  type="file"
                  multiple
                  onChange={(e) => setFiles(e.target.files)}
                  style={{ display: "none" }}
                />
                <div style={{ fontWeight: 900, marginBottom: 6 }}>
                  {selected.length ? `${selected.length} file(s) selected` : "Click to choose files"}
                </div>
                <div className="muted" style={{ fontSize: 12 }}>
                  PDFs and text files work best for indexing.
                </div>
              </label>

              {selected.length > 0 && (
                <div className="card" style={{ marginTop: 12, overflow: "hidden" }}>
                  <div style={{ padding: 10, fontSize: 12 }} className="muted">
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
                          borderTop: "1px solid var(--card-border)",
                        }}
                      >
                        <div style={{ minWidth: 0 }}>
                          <div style={{ fontSize: 13, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                            {f.name}
                          </div>
                          <div className="muted" style={{ fontSize: 12 }}>
                            {humanBytes(f.size)}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div style={{ flex: "0 0 300px" }}>
              <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>
                Actions
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <button
                  onClick={handleUpload}
                  className="btn btn-primary"
                  disabled={busy !== "" || selected.length === 0}
                >
                  {busy === "upload" ? "Uploading…" : "1) Upload"}
                </button>

                <button onClick={handleBuild} className="btn" disabled={busy !== ""}>
                  {busy === "build" ? "Building…" : "2) Build"}
                </button>

                <button
                  onClick={handleDeploy}
                  className="btn"
                  disabled={busy !== "" || !edgeOnline}
                  title={!edgeOnline ? "Edge device must be online" : ""}
                >
                  {busy === "deploy" ? "Deploying…" : "3) Deploy"}
                </button>

                {!isAdmin && (
                  <div className="muted" style={{ fontSize: 12, marginTop: 6 }}>
                    Admins can later get delete/mkdir controls if you want.
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="status-box mono" style={{ fontSize: 13, opacity: 0.95 }}>
            {status ? `> ${status}` : "> Idle"}
          </div>
        </div>
      </div>
    </div>
  );
}