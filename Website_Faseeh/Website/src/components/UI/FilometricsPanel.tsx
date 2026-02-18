import "../../styles/dashboard.css";

type Metric = {
    label: string;
    value: string;
    sub?: string;
    status?: "good" | "warn" | "bad";
};

const metrics: Metric[] = [
    { label: "Battery", value: "—", sub: "%", status: "warn" },
    { label: "Ping", value: "—", sub: "ms", status: "warn" },
    { label: "CPU", value: "—", sub: "%", status: "warn" },
    { label: "Temp", value: "—", sub: "°C", status: "warn" },
    { label: "Uptime", value: "—", sub: "", status: "good" },
    { label: "Mode", value: "—", sub: "", status: "good" },
];

function dotColor(status?: Metric["status"]) {
    if (status === "good") return "var(--status-good)";
    if (status === "warn") return "var(--status-warn)";
    if (status === "bad") return "var(--status-bad)";
    return "var(--card-border)";
}

export default function FilometricsPanel() {
    return (
        <section className="card dash-card">
            <div className="dash-title-row">
                <h2 className="dash-title">Filometrics</h2>
                <span className="dash-subtitle">Live system stats</span>
            </div>

            <div className="filo-grid">
                {metrics.map((m) => (
                    <div className="filo-item" key={m.label}>
                        <div className="filo-top">
                            <div className="filo-label">{m.label}</div>
                            <div className="filo-dot" style={{ background: dotColor(m.status) }} />
                        </div>

                        <div className="filo-value">{m.value}</div>
                        <div className="filo-sub">{m.sub || "\u00A0"}</div>
                    </div>
                ))}
            </div>
        </section>
    );
}
