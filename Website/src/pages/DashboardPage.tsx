import { useEffect, useMemo, useState } from "react";
import "../styles/dashboard.css";
import robotImage from "../assets/robot.png";
import { loadDashboardMock, mutateDashboard, type DashboardData } from "../services/mockDashboard";

function dotColor(status: "OK" | "WARN" | "BAD") {
  if (status === "OK") return "var(--status-good)";
  if (status === "WARN") return "var(--status-warn)";
  return "var(--status-bad)";
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);

  useEffect(() => {
    let alive = true;

    (async () => {
      const initial = await loadDashboardMock();
      if (alive) setData(initial);
    })();

    const id = setInterval(() => {
      setData((prev) => (prev ? mutateDashboard(prev) : prev));
    }, 1000);

    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  const updatedLabel = useMemo(() => {
    if (!data) return "";
    const d = new Date(data.updatedAt);
    return d.toLocaleTimeString();
  }, [data?.updatedAt]);

  return (
    <div className="dashboard-page">
      <div className="aura-header">
        <div className="aura-panel">
          <img src={robotImage} alt="AURA" className="aura-img" />
          <div className="aura-text">
            <h1 className="aura-title">{data?.robot.name ?? "AURA"}</h1>
            <div className="aura-sub">
              Status: <b>{data?.robot.status ?? "—"}</b>
              {updatedLabel ? <> • Updated {updatedLabel}</> : null}
            </div>
          </div>
        </div>
      </div>

      <section className="dashboard-section">
        <div className="dash-title-row">
          <h2 className="dash-title">Filometrics</h2>
          <div className="dash-subtitle">Live mock values (updates every second)</div>
        </div>

        <div className="filo-grid">
          <FiloCard label="Battery" value={data ? `${data.system.batteryPct.toFixed(1)}%` : "—"} sub="Robot power" />
          <FiloCard label="CPU Temp" value={data ? `${data.system.cpuTempC.toFixed(1)}°C` : "—"} sub="Jetson SoC" />
          <FiloCard label="RAM Usage" value={data ? `${data.system.ramPct.toFixed(1)}%` : "—"} sub="Memory load" />
          <FiloCard label="Wi-Fi" value={data ? `${data.system.wifiDbm.toFixed(0)} dBm` : "—"} sub="Signal strength" />
          <FiloCard label="Weight" value={data ? `${data.system.weightLb.toFixed(2)} lb` : "—"} sub="Payload sensor" />
          <FiloCard label="Uptime" value={data ? formatUptime(data.robot.uptimeSec) : "—"} sub="Since boot" />
        </div>
      </section>

      <section className="dashboard-section">
        <div className="dash-title-row">
          <h2 className="dash-title">System Health</h2>
          <div className="dash-subtitle">Quick status checks</div>
        </div>

        <div className="filo-grid">
          <HealthCard label="Motors" status={data?.health.motors} />
          <HealthCard label="Sensors" status={data?.health.sensors} />
          <HealthCard label="Thermals" status={data?.health.thermals} />
        </div>
      </section>
    </div>
  );
}

function FiloCard({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="filo-item">
      <div className="filo-top">
        <div className="filo-label">{label}</div>
        <div className="filo-dot" style={{ background: "var(--accent)" }} />
      </div>
      <div className="filo-value">{value}</div>
      <div className="filo-sub">{sub}</div>
    </div>
  );
}

function HealthCard({ label, status }: { label: string; status?: "OK" | "WARN" | "BAD" }) {
  const s = status ?? "OK";
  return (
    <div className="filo-item">
      <div className="filo-top">
        <div className="filo-label">{label}</div>
        <div className="filo-dot" style={{ background: dotColor(s) }} />
      </div>
      <div className="filo-value">{s}</div>
      <div className="filo-sub">Overall condition</div>
    </div>
  );
}

function formatUptime(sec: number) {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  return `${h}h ${m}m ${s}s`;
}
