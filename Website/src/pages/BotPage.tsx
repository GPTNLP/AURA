import React from "react";

const FRIEND_ML_URL =
  (import.meta.env.VITE_ML_BOT_URL as string | undefined) || "http://127.0.0.1:9000";

export default function BotPage() {
  return (
    <div style={{ width: "100%" }}>
      <div style={{ maxWidth: 1200, margin: "0 auto" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
          <div>
            <h2 style={{ margin: 0 }}>Bot</h2>
            <div style={{ fontSize: 12, opacity: 0.75, marginTop: 4 }}>
              Embedded ML UI (set <span style={{ fontFamily: "monospace" }}>VITE_ML_BOT_URL</span>)
            </div>
          </div>

          <a
            href={FRIEND_ML_URL}
            target="_blank"
            rel="noreferrer"
            style={{
              padding: "10px 14px",
              borderRadius: 12,
              border: `1px solid var(--card-border)`,
              textDecoration: "none",
              color: "var(--text)",
              background: "var(--card-bg)",
              boxShadow: "var(--shadow)",
            }}
          >
            Open in new tab →
          </a>
        </div>

        <div
          style={{
            marginTop: 14,
            borderRadius: 14,
            border: `1px solid var(--card-border)`,
            overflow: "hidden",
            background: "var(--card-bg)",
            boxShadow: "var(--shadow)",
          }}
        >
          <iframe
            title="ML Bot"
            src={FRIEND_ML_URL}
            style={{ width: "100%", height: "78vh", border: "none", background: "transparent" }}
          />
        </div>

        <div style={{ marginTop: 10, fontSize: 12, opacity: 0.75 }}>
          Using: <span style={{ fontFamily: "monospace" }}>{FRIEND_ML_URL}</span>
        </div>
      </div>
    </div>
  );
}