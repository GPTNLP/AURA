import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";

type ChatMsg = {
  role: "user" | "ai" | "error";
  content: string;
  sources?: string[];
};

type ChatResponse = {
  answer?: string;
  sources?: string[];
  detail?: string;
  message?: string;
  inserted_chunks?: number;
  skipped_files?: number;
  files_found?: number;
};

export default function SimulatorPage() {
  const [query, setQuery] = useState("");
  const [history, setHistory] = useState<ChatMsg[]>([]);
  const [loading, setLoading] = useState(false);

  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [building, setBuilding] = useState(false);

  const [apiOnline, setApiOnline] = useState<boolean | null>(null);
  const [statusText, setStatusText] = useState<string>("");

  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const API_URL = useMemo(() => {
    const env = (import.meta as unknown as { env?: Record<string, string> }).env;
    return env?.VITE_API_URL?.trim() || "http://localhost:9000";
  }, []);

  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  // Auto-scroll chat
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [history, loading]);

  // Ping backend health
  useEffect(() => {
    let cancelled = false;

    const ping = async () => {
      try {
        const res = await fetch(`${API_URL}/health`, { method: "GET" });
        if (!cancelled) setApiOnline(res.ok);
      } catch {
        if (!cancelled) setApiOnline(false);
      }
    };

    ping();
    const t = setInterval(ping, 8000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [API_URL]);

  const handleUpload = async () => {
    if (selectedFiles.length === 0 || uploading) return;

    setUploading(true);
    setStatusText("");

    try {
      const fd = new FormData();
      for (const f of selectedFiles) fd.append("files", f);

      const res = await fetch(`${API_URL}/api/upload`, {
        method: "POST",
        body: fd,
      });

      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.detail || data?.message || "Upload failed");

      setStatusText(`✅ Uploaded ${selectedFiles.length} file(s). Now click “Build DB”.`);
    } catch (err: any) {
      setStatusText(`❌ Upload error: ${err?.message || String(err)}`);
    } finally {
      setUploading(false);
    }
  };

  const handleBuild = async () => {
    if (building) return;
    setBuilding(true);
    setStatusText("");

    try {
      const res = await fetch(`${API_URL}/api/build?force_reload=true`, {
        method: "POST",
      });

      const data = (await res.json().catch(() => null)) as ChatResponse | null;
      if (!res.ok) throw new Error(data?.detail || data?.message || "Build failed");

      setStatusText(
        `✅ DB built. Files: ${data?.files_found ?? "?"}. Inserted chunks: ${
          data?.inserted_chunks ?? "?"
        }. Skipped files: ${data?.skipped_files ?? "?"}.`
      );
    } catch (err: any) {
      setStatusText(`❌ Build error: ${err?.message || String(err)}`);
    } finally {
      setBuilding(false);
    }
  };

  const handleSearch = async () => {
    const q = query.trim();
    if (!q || loading) return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setHistory((prev) => [...prev, { role: "user", content: q }]);
    setQuery("");
    setLoading(true);

    try {
      const res = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q }),
        signal: controller.signal,
      });

      let data: ChatResponse | null = null;
      try {
        data = (await res.json()) as ChatResponse;
      } catch {
        data = null;
      }

      if (!res.ok) {
        const msg = data?.detail || data?.message || `Request failed (${res.status})`;
        throw new Error(msg);
      }

      const answer =
        typeof data?.answer === "string" && data.answer.trim()
          ? data.answer
          : "(No answer returned)";

      const sources = Array.isArray(data?.sources) ? data!.sources : [];
      setHistory((prev) => [...prev, { role: "ai", content: answer, sources }]);
    } catch (err: any) {
      if (err?.name === "AbortError") return;
      setHistory((prev) => [
        ...prev,
        { role: "error", content: `Simulation Error: ${err?.message || String(err)}` },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const statusDotClass =
    apiOnline === null ? "bg-slate-300" : apiOnline ? "bg-emerald-500" : "bg-red-500";

  return (
    <div style={{ padding: 18 }}>
      <div
        style={{
          maxWidth: 1100,
          margin: "0 auto",
          background: "var(--card-bg)",
          border: "1px solid var(--card-border)",
          borderRadius: "var(--card-radius)",
          overflow: "hidden",
          boxShadow: "var(--shadow)",
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: 18,
            background: "color-mix(in srgb, var(--card-bg) 80%, var(--accent-soft))",
            borderBottom: "1px solid var(--card-border)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
          }}
        >
          <div style={{ minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
              <h1 style={{ margin: 0, fontSize: 22, fontWeight: 900, color: "var(--text)" }}>
                Edge Device Simulator
              </h1>

              <span
                style={{
                  fontSize: 12,
                  padding: "4px 10px",
                  borderRadius: 999,
                  border: "1px solid var(--card-border)",
                  background: "color-mix(in srgb, var(--card-bg) 85%, var(--accent-soft))",
                  color: "var(--muted-text)",
                  fontFamily:
                    "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                }}
              >
                API: {API_URL}
              </span>
            </div>

            <p style={{ margin: "6px 0 0", color: "var(--muted-text)", fontSize: 13 }}>
              Upload documents, build the local index, and test the RAG pipeline before Jetson
              deployment.
            </p>
          </div>

          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              padding: "6px 10px",
              borderRadius: 999,
              border: "1px solid var(--card-border)",
              background: "color-mix(in srgb, var(--card-bg) 85%, var(--accent-soft))",
              color: "var(--muted-text)",
              fontSize: 12,
              fontWeight: 800,
            }}
            title="Backend status"
          >
            <span className={`inline-block w-2.5 h-2.5 rounded-full ${statusDotClass}`} />
            {apiOnline === null ? "Checking…" : apiOnline ? "Backend online" : "Backend offline"}
          </span>
        </div>

        {/* Controls */}
        <div
          style={{
            padding: 16,
            borderBottom: "1px solid var(--card-border)",
            display: "grid",
            gridTemplateColumns: "1fr auto auto",
            gap: 10,
            alignItems: "center",
          }}
        >
          <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            <input
              type="file"
              multiple
              onChange={(e) => setSelectedFiles(Array.from(e.target.files ?? []))}
              style={{
                maxWidth: 520,
                width: "100%",
                padding: 10,
                borderRadius: 12,
                border: "1px solid var(--card-border)",
                background: "var(--card-bg)",
                color: "var(--text)",
              }}
            />
            <span style={{ color: "var(--muted-text)", fontSize: 12 }}>
              {selectedFiles.length > 0 ? `${selectedFiles.length} selected` : "Select docs to upload"}
            </span>
          </div>

          <button
            onClick={handleUpload}
            disabled={uploading || selectedFiles.length === 0}
            style={{
              padding: "10px 14px",
              borderRadius: 12,
              border: "1px solid var(--card-border)",
              background: "var(--card-bg)",
              color: "var(--text)",
              fontWeight: 900,
              cursor: uploading || selectedFiles.length === 0 ? "not-allowed" : "pointer",
              boxShadow: "none",
            }}
            title="Upload documents to backend staging folder"
          >
            {uploading ? "Uploading…" : "Upload Docs"}
          </button>

          <button
            onClick={handleBuild}
            disabled={building}
            style={{
              padding: "10px 14px",
              borderRadius: 12,
              border: "1px solid rgba(0,0,0,0)",
              background: "var(--accent)",
              color: "white",
              fontWeight: 900,
              cursor: building ? "not-allowed" : "pointer",
              boxShadow: "var(--shadow)",
              opacity: building ? 0.75 : 1,
            }}
            title="Build the LightRAG index"
          >
            {building ? "Building…" : "Build DB"}
          </button>
        </div>

        {/* Status line */}
        {statusText && (
          <div style={{ padding: "10px 16px", borderBottom: "1px solid var(--card-border)" }}>
            <div
              style={{
                padding: "10px 12px",
                borderRadius: 12,
                background: "color-mix(in srgb, var(--card-bg) 85%, var(--accent-soft))",
                color: "var(--muted-text)",
                fontSize: 13,
              }}
            >
              {statusText}
            </div>
          </div>
        )}

        {/* Chat */}
        <div
          ref={scrollRef}
          style={{
            height: 520,
            overflowY: "auto",
            padding: 16,
            background: "color-mix(in srgb, var(--bg) 85%, var(--accent-soft))",
          }}
        >
          {history.length === 0 && !loading && (
            <div style={{ textAlign: "center", color: "var(--muted-text)", padding: "60px 16px" }}>
              <div style={{ fontSize: 14, fontWeight: 900, marginBottom: 6 }}>
                Ready when you are.
              </div>
              <div style={{ fontSize: 13 }}>
                Upload docs → Build DB → Ask something like:
                <span style={{ fontFamily: "monospace" }}> “What is Ohm’s law?”</span>
              </div>
            </div>
          )}

          {history.map((msg, i) => {
            const isUser = msg.role === "user";
            const isError = msg.role === "error";

            const bubbleStyle: CSSProperties = {
              maxWidth: "78%",
              padding: "12px 14px",
              borderRadius: 16,
              whiteSpace: "pre-wrap",
              lineHeight: 1.45,
              fontSize: 14,
              boxShadow: "var(--shadow)",
              border: "1px solid var(--card-border)",
              background: "var(--card-bg)",
              color: "var(--text)",
            };

            if (isUser) {
              bubbleStyle.background = "var(--accent)";
              bubbleStyle.color = "white";
              bubbleStyle.border = "1px solid rgba(0,0,0,0)";
              bubbleStyle.borderBottomRightRadius = 6;
            } else if (isError) {
              bubbleStyle.background = "color-mix(in srgb, var(--status-bad) 12%, var(--card-bg))";
              bubbleStyle.color = "color-mix(in srgb, var(--status-bad) 80%, var(--text))";
              bubbleStyle.border = "1px solid color-mix(in srgb, var(--status-bad) 35%, var(--card-border))";
              bubbleStyle.borderBottomLeftRadius = 6;
            } else {
              bubbleStyle.borderBottomLeftRadius = 6;
            }

            return (
              <div
                key={i}
                style={{
                  display: "flex",
                  justifyContent: isUser ? "flex-end" : "flex-start",
                  marginBottom: 12,
                }}
              >
                <div style={bubbleStyle}>
                  {msg.content}
                  {msg.sources && msg.sources.length > 0 && (
                    <div
                      style={{
                        marginTop: 10,
                        paddingTop: 10,
                        borderTop: "1px solid var(--card-border)",
                        fontSize: 12,
                        opacity: 0.9,
                        fontFamily:
                          "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                      }}
                    >
                      <strong>Sources:</strong> {msg.sources.join(", ")}
                    </div>
                  )}
                </div>
              </div>
            );
          })}

          {loading && (
            <div style={{ display: "flex", justifyContent: "flex-start", marginBottom: 12 }}>
              <div
                style={{
                  maxWidth: "78%",
                  padding: "12px 14px",
                  borderRadius: 16,
                  borderBottomLeftRadius: 6,
                  border: "1px solid var(--card-border)",
                  background: "var(--card-bg)",
                  color: "var(--muted-text)",
                  fontSize: 14,
                  boxShadow: "var(--shadow)",
                }}
              >
                AURA is thinking…
              </div>
            </div>
          )}
        </div>

        {/* Input */}
        <div
          style={{
            padding: 14,
            borderTop: "1px solid var(--card-border)",
            background: "var(--card-bg)",
            display: "flex",
            gap: 10,
            alignItems: "center",
          }}
        >
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask a question about the documents…"
            disabled={loading}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSearch();
              }
            }}
            style={{
              flex: 1,
              padding: "12px 12px",
              borderRadius: 12,
              border: "1px solid var(--card-border)",
              background: "var(--card-bg)",
              color: "var(--text)",
              outline: "none",
            }}
          />

          <button
            onClick={handleSearch}
            disabled={loading || !query.trim()}
            style={{
              padding: "12px 16px",
              borderRadius: 12,
              border: "1px solid rgba(0,0,0,0)",
              background: "var(--accent)",
              color: "white",
              fontWeight: 900,
              cursor: loading || !query.trim() ? "not-allowed" : "pointer",
              opacity: loading || !query.trim() ? 0.6 : 1,
              boxShadow: "var(--shadow)",
            }}
          >
            Test Model
          </button>
        </div>
      </div>
    </div>
  );
}