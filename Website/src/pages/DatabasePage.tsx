import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../services/authService";
import "../styles/page-ui.css";

const API_BASE =
  (import.meta.env.VITE_AUTH_API_BASE as string | undefined) ||
  "http://127.0.0.1:9000";

type TreeNode = {
  name: string;
  type: "dir" | "file";
  children?: TreeNode[];
};

type TreeResponse = {
  tree?: TreeNode;
};

function joinPath(parent: string, name: string) {
  if (!parent) return name;
  return `${parent}/${name}`.replaceAll("//", "/");
}

function humanCount(n: number) {
  if (!Number.isFinite(n)) return "-";
  return `${n}`;
}

export default function DatabasePage() {
  const { token, user } = useAuth();
  const isAdmin = user?.role === "admin";

  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState<
    | ""
    | "tree"
    | "upload"
    | "mkdir"
    | "move"
    | "delete"
    | "db-create"
    | "db-build"
    | "db-stats"
  >("");

  // Documents
  const [tree, setTree] = useState<TreeNode | null>(null);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({ "": true });
  const [selectedPath, setSelectedPath] = useState<string>(""); // folder path relative to documents root

  // Upload
  const [files, setFiles] = useState<FileList | null>(null);
  const selectedFiles = useMemo(() => (files ? Array.from(files) : []), [files]);

  // DBs
  const [dbList, setDbList] = useState<string[]>([]);
  const [activeDb, setActiveDb] = useState<string>("");
  const [newDbName, setNewDbName] = useState<string>("");

  // Folder selection for DB build
  const [folderChecks, setFolderChecks] = useState<Record<string, boolean>>({});
  const [dbStats, setDbStats] = useState<any>(null);

  // ✅ Fix: always return a real Headers object (never { Authorization?: undefined })
  const authHeaders = useMemo(() => {
    const h = new Headers();
    if (token) h.set("Authorization", `Bearer ${token}`);
    return h;
  }, [token]);

  const refreshTree = async () => {
    setBusy("tree");
    try {
      const res = await fetch(`${API_BASE}/api/documents/tree`, {
        headers: authHeaders,
      });
      const data = (await res.json().catch(() => null)) as TreeResponse | null;
      if (!res.ok) throw new Error("Failed to load documents tree");
      setTree((data?.tree as TreeNode) || null);
    } catch (e: any) {
      setStatus(`Error: ${e?.message || String(e)}`);
    } finally {
      setBusy("");
    }
  };

  const refreshDatabases = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/databases`, {
        headers: authHeaders,
      });
      const data = await res.json().catch(() => null);
      const list = Array.isArray(data?.databases) ? (data.databases as string[]) : [];
      setDbList(list);
      if (!activeDb && list.length) setActiveDb(list[0]);
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    refreshTree();
    refreshDatabases();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---------- Documents actions ----------
  const doMkdir = async () => {
    const name = prompt("Folder name (created inside selected folder):");
    if (!name) return;

    const path = selectedPath ? `${selectedPath}/${name}` : name;

    setBusy("mkdir");
    setStatus("Creating folder…");
    try {
      const headers = new Headers(authHeaders);
      headers.set("Content-Type", "application/json");

      const res = await fetch(`${API_BASE}/api/documents/mkdir`, {
        method: "POST",
        headers,
        body: JSON.stringify({ path }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.detail || "mkdir failed");
      setStatus(`✅ Created folder: ${path}`);
      await refreshTree();
    } catch (e: any) {
      setStatus(`❌ ${e?.message || String(e)}`);
    } finally {
      setBusy("");
    }
  };

  const doUpload = async () => {
    if (!selectedFiles.length) return;

    setBusy("upload");
    setStatus("Uploading…");

    try {
      const fd = new FormData();
      for (const f of selectedFiles) fd.append("files", f);

      const url = new URL(`${API_BASE}/api/documents/upload`);
      if (selectedPath) url.searchParams.set("path", selectedPath);

      const res = await fetch(url.toString(), {
        method: "POST",
        headers: authHeaders, // DON'T set content-type for FormData
        body: fd,
      });

      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.detail || "Upload failed");

      setStatus(`✅ Uploaded ${selectedFiles.length} file(s) into "${selectedPath || "documents"}"`);
      setFiles(null);
      await refreshTree();
    } catch (e: any) {
      setStatus(`❌ ${e?.message || String(e)}`);
    } finally {
      setBusy("");
    }
  };

  const doDelete = async () => {
    const p = prompt(
      "Enter path to delete (relative to documents). مثال: physics/unit1/file.pdf",
      selectedPath || ""
    );
    if (!p) return;
    if (!confirm(`Delete "${p}" ?`)) return;

    setBusy("delete");
    setStatus("Deleting…");
    try {
      const url = new URL(`${API_BASE}/api/documents/delete`);
      url.searchParams.set("path", p);

      const res = await fetch(url.toString(), {
        method: "DELETE",
        headers: authHeaders,
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.detail || "Delete failed");
      setStatus(`✅ Deleted: ${p}`);
      await refreshTree();
    } catch (e: any) {
      setStatus(`❌ ${e?.message || String(e)}`);
    } finally {
      setBusy("");
    }
  };

  const doMove = async () => {
    const src = prompt("Move FROM (relative to documents):", "");
    if (!src) return;
    const dst = prompt("Move TO (relative to documents):", "");
    if (!dst) return;

    setBusy("move");
    setStatus("Moving…");
    try {
      const headers = new Headers(authHeaders);
      headers.set("Content-Type", "application/json");

      const res = await fetch(`${API_BASE}/api/documents/move`, {
        method: "POST",
        headers,
        body: JSON.stringify({ src, dst }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.detail || "Move failed");
      setStatus(`✅ Moved: ${src} → ${dst}`);
      await refreshTree();
    } catch (e: any) {
      setStatus(`❌ ${e?.message || String(e)}`);
    } finally {
      setBusy("");
    }
  };

  // ---------- DB actions ----------
  const doCreateDb = async () => {
    const name = newDbName.trim();
    if (!name) {
      setStatus("❌ Enter a database name first.");
      return;
    }

    const folders = Object.entries(folderChecks)
      .filter(([, v]) => v)
      .map(([k]) => k);

    setBusy("db-create");
    setStatus("Creating database…");
    try {
      const headers = new Headers(authHeaders);
      headers.set("Content-Type", "application/json");

      const res = await fetch(`${API_BASE}/api/databases/create`, {
        method: "POST",
        headers,
        body: JSON.stringify({ name, folders }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.detail || "Create DB failed");
      setStatus(`✅ Created DB: ${name}`);
      setActiveDb(name);
      setNewDbName("");
      await refreshDatabases();
    } catch (e: any) {
      setStatus(`❌ ${e?.message || String(e)}`);
    } finally {
      setBusy("");
    }
  };

  const doBuildDb = async () => {
    if (!activeDb) {
      setStatus("❌ Choose a database first.");
      return;
    }

    const folders = Object.entries(folderChecks)
      .filter(([, v]) => v)
      .map(([k]) => k);

    if (!folders.length) {
      setStatus("❌ Select at least one folder to build from.");
      return;
    }

    setBusy("db-build");
    setStatus("Building database (can take a bit)…");
    try {
      const headers = new Headers(authHeaders);
      headers.set("Content-Type", "application/json");

      const res = await fetch(`${API_BASE}/api/databases/build`, {
        method: "POST",
        headers,
        body: JSON.stringify({ name: activeDb, folders, force: true }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.detail || "Build failed");

      setStatus(
        `✅ Built "${activeDb}". Files: ${data?.files_found ?? "?"}, chunks: ${
          data?.inserted_chunks ?? "?"
        }, skipped: ${data?.skipped_files ?? "?"}`
      );
      await loadDbStats(activeDb);
    } catch (e: any) {
      setStatus(`❌ ${e?.message || String(e)}`);
    } finally {
      setBusy("");
    }
  };

  const loadDbStats = async (name: string) => {
    if (!name) return;
    setBusy("db-stats");
    try {
      const res = await fetch(`${API_BASE}/api/databases/${encodeURIComponent(name)}/stats`, {
        headers: authHeaders,
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.detail || "Stats failed");
      setDbStats(data);
    } catch {
      setDbStats(null);
    } finally {
      setBusy("");
    }
  };

  useEffect(() => {
    if (activeDb) loadDbStats(activeDb);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeDb]);

  // ---------- Tree rendering ----------
  const toggle = (path: string) => {
    setExpanded((p) => ({ ...p, [path]: !p[path] }));
  };

  const renderNode = (node: TreeNode, parentPath: string) => {
    if (node.type !== "dir") return null;

    const children = node.children || [];
    return (
      <div>
        {children.map((ch) => {
          const chPath = joinPath(parentPath, ch.name);
          const isOpen = expanded[chPath] ?? false;

          if (ch.type === "dir") {
            const checked = !!folderChecks[chPath];

            return (
              <div key={chPath} style={{ marginTop: 8 }}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    padding: "8px 10px",
                    borderRadius: 12,
                    border: "1px solid var(--card-border)",
                    background:
                      selectedPath === chPath
                        ? "color-mix(in srgb, var(--accent) 10%, var(--card-bg))"
                        : "var(--card-bg)",
                    cursor: "pointer",
                  }}
                  onClick={() => setSelectedPath(chPath)}
                  title={chPath}
                >
                  <button
                    className="btn"
                    style={{
                      padding: "6px 10px",
                      borderRadius: 10,
                      fontWeight: 900,
                      background: "color-mix(in srgb, var(--card-bg) 80%, var(--accent-soft))",
                    }}
                    onClick={(e) => {
                      e.stopPropagation();
                      toggle(chPath);
                    }}
                  >
                    {isOpen ? "▾" : "▸"}
                  </button>

                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 900, fontSize: 13, color: "var(--text)" }}>
                      {ch.name}
                    </div>
                    <div
                      className="muted"
                      style={{
                        fontSize: 12,
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                      }}
                    >
                      {chPath}
                    </div>
                  </div>

                  <label
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      fontSize: 12,
                      color: "var(--muted-text)",
                      fontWeight: 900,
                      userSelect: "none",
                    }}
                    onClick={(e) => e.stopPropagation()}
                    title="Include this folder when building the active database"
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={(e) =>
                        setFolderChecks((p) => ({ ...p, [chPath]: e.target.checked }))
                      }
                    />
                    Include
                  </label>
                </div>

                {isOpen && (
                  <div style={{ marginLeft: 22, marginTop: 8 }}>
                    {renderNode(ch, chPath)}

                    {(ch.children || [])
                      .filter((x) => x.type === "file")
                      .map((f) => (
                        <div
                          key={joinPath(chPath, f.name)}
                          style={{
                            padding: "8px 10px",
                            borderRadius: 12,
                            border: "1px solid var(--card-border)",
                            background: "color-mix(in srgb, var(--card-bg) 90%, var(--accent-soft))",
                            marginTop: 8,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            gap: 10,
                          }}
                          title={joinPath(chPath, f.name)}
                        >
                          <div style={{ minWidth: 0 }}>
                            <div style={{ fontSize: 13, fontWeight: 800, color: "var(--text)" }}>
                              {f.name}
                            </div>
                            <div className="muted" style={{ fontSize: 12 }}>
                              {joinPath(chPath, f.name)}
                            </div>
                          </div>
                        </div>
                      ))}
                  </div>
                )}
              </div>
            );
          }

          return null;
        })}
      </div>
    );
  };

  return (
    <div className="page-shell">
      <div className="page-wrap">
        <div className="page-header">
          <div>
            <h2 className="page-title">Database</h2>
            <div className="page-subtitle">Manage documents → select folders → build named databases</div>
          </div>

          <div className="badge" title="Role">
            Role:
            <span
              style={{
                marginLeft: 6,
                padding: "4px 10px",
                borderRadius: 999,
                border: "1px solid var(--card-border)",
                background: "color-mix(in srgb, var(--card-bg) 85%, var(--accent-soft))",
                color: "var(--muted-text)",
                fontWeight: 900,
              }}
            >
              {isAdmin ? "ADMIN" : "USER"}
            </span>
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1.2fr 0.8fr", gap: 14 }}>
          {/* Documents */}
          <div className="card card-pad">
            <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
              <div>
                <div style={{ fontWeight: 900, fontSize: 14 }}>Documents</div>
                <div className="muted" style={{ fontSize: 12 }}>
                  Selected folder:{" "}
                  <span style={{ fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" }}>
                    {selectedPath || "(root)"}
                  </span>
                </div>
              </div>

              <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                <button className="btn" disabled={busy !== ""} onClick={refreshTree}>
                  Refresh
                </button>
                <button className="btn" disabled={busy !== ""} onClick={doMkdir}>
                  + Folder
                </button>
                <button className="btn" disabled={busy !== ""} onClick={doMove}>
                  Move/Rename
                </button>
                <button className="btn" disabled={busy !== ""} onClick={doDelete}>
                  Delete
                </button>
              </div>
            </div>

            <div style={{ marginTop: 12 }}>
              <label className="panel" style={{ display: "block", cursor: "pointer" }}>
                <input
                  type="file"
                  multiple
                  onChange={(e) => setFiles(e.target.files)}
                  style={{ display: "none" }}
                />
                <div style={{ fontWeight: 900, marginBottom: 6 }}>
                  {selectedFiles.length
                    ? `${selectedFiles.length} file(s) selected`
                    : "Click to choose files to upload"}
                </div>
                <div className="muted" style={{ fontSize: 12 }}>
                  Uploads go into the selected folder above.
                </div>
              </label>

              <div style={{ display: "flex", gap: 10, marginTop: 10, flexWrap: "wrap" }}>
                <button
                  onClick={doUpload}
                  className="btn btn-primary"
                  disabled={busy !== "" || selectedFiles.length === 0}
                >
                  {busy === "upload" ? "Uploading…" : "Upload to Selected Folder"}
                </button>

                <div className="muted" style={{ fontSize: 12, alignSelf: "center" }}>
                  Tip: check “Include” on folders you want in databases.
                </div>
              </div>
            </div>

            <div style={{ marginTop: 14 }}>
              <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>
                Folder tree (check folders to include in DB build)
              </div>

              <div style={{ maxHeight: 520, overflow: "auto" }}>
                {tree ? renderNode(tree, "") : <div className="muted">No documents yet.</div>}
              </div>
            </div>
          </div>

          {/* Databases */}
          <div className="card card-pad">
            <div style={{ fontWeight: 900, fontSize: 14 }}>Databases</div>
            <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
              Build a database from any selected folders. Chat uses the DB name.
            </div>

            <div style={{ marginTop: 12, display: "flex", gap: 10, flexWrap: "wrap" }}>
              <select
                value={activeDb}
                onChange={(e) => setActiveDb(e.target.value)}
                style={{
                  flex: 1,
                  minWidth: 220,
                  padding: "10px 12px",
                  borderRadius: 12,
                  border: "1px solid var(--card-border)",
                  background: "var(--card-bg)",
                  color: "var(--text)",
                  fontWeight: 900,
                }}
                disabled={dbList.length === 0}
              >
                {dbList.length === 0 ? (
                  <option value="">No databases yet</option>
                ) : (
                  dbList.map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))
                )}
              </select>

              <button className="btn" disabled={busy !== ""} onClick={refreshDatabases}>
                Refresh
              </button>
            </div>

            <div style={{ marginTop: 12 }}>
              <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>
                Create new DB (uses checked folders)
              </div>
              <div style={{ display: "flex", gap: 10 }}>
                <input
                  value={newDbName}
                  onChange={(e) => setNewDbName(e.target.value)}
                  placeholder="db name (e.g., ecen214)"
                  style={{
                    flex: 1,
                    padding: "10px 12px",
                    borderRadius: 12,
                    border: "1px solid var(--card-border)",
                    background: "var(--card-bg)",
                    color: "var(--text)",
                    outline: "none",
                    fontWeight: 800,
                  }}
                />
                <button className="btn btn-primary" disabled={busy !== ""} onClick={doCreateDb}>
                  {busy === "db-create" ? "Creating…" : "Create"}
                </button>
              </div>
            </div>

            <div style={{ marginTop: 14 }}>
              <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>
                Build selected DB (rebuilds from checked folders)
              </div>
              <button
                className="btn"
                disabled={busy !== "" || !activeDb}
                onClick={doBuildDb}
                style={{ width: "100%" }}
              >
                {busy === "db-build" ? "Building…" : `Build "${activeDb || "DB"}"`}
              </button>
            </div>

            {dbStats && (
              <div className="card" style={{ marginTop: 14, overflow: "hidden" }}>
                <div style={{ padding: 12, borderBottom: "1px solid var(--card-border)" }}>
                  <div style={{ fontWeight: 900 }}>Stats</div>
                  <div className="muted" style={{ fontSize: 12 }}>
                    {activeDb}
                  </div>
                </div>
                <div style={{ padding: 12, fontSize: 13 }}>
                  <div className="muted" style={{ marginBottom: 6 }}>
                    chunks: <b>{humanCount(dbStats?.stats?.chunk_count ?? 0)}</b>
                  </div>
                  <div className="muted" style={{ marginBottom: 6 }}>
                    file:{" "}
                    <span
                      style={{
                        fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                      }}
                    >
                      {dbStats?.stats?.vdb_path || "-"}
                    </span>
                  </div>
                  <div className="muted">
                    model: <b>{dbStats?.config?.llm_model || "-"}</b>
                    {" · "}
                    embed: <b>{dbStats?.config?.embed_model || "-"}</b>
                  </div>
                </div>
              </div>
            )}

            <div className="status-box mono" style={{ fontSize: 13, opacity: 0.95, marginTop: 14 }}>
              {status ? `> ${status}` : "> Idle"}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}