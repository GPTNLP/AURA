export type DashboardData = {
  updatedAt: string;
  robot: { name: string; status: "ONLINE" | "OFFLINE"; uptimeSec: number };
  system: {
    batteryPct: number;
    cpuTempC: number;
    ramPct: number;
    wifiDbm: number;
    weightLb: number;
  };
  health: { motors: "OK" | "WARN" | "BAD"; sensors: "OK" | "WARN" | "BAD"; thermals: "OK" | "WARN" | "BAD" };
};

function clamp(n: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, n));
}

function jitter(n: number, amt: number) {
  return n + (Math.random() * 2 - 1) * amt;
}

export async function loadDashboardMock(): Promise<DashboardData> {
  // Vite can fetch files from /src only if served. Better: put mock files in /public.
  // BUT if you want to keep it in src, import it directly:
  const mod = await import("../mock-api/dashboard.json");
  return mod.default as DashboardData;
}

export function mutateDashboard(d: DashboardData): DashboardData {
  const next: DashboardData = structuredClone(d);

  next.updatedAt = new Date().toISOString();
  next.robot.uptimeSec = next.robot.uptimeSec + 1;

  next.system.batteryPct = clamp(jitter(next.system.batteryPct, 0.25), 0, 100);
  next.system.cpuTempC = clamp(jitter(next.system.cpuTempC, 0.35), 20, 95);
  next.system.ramPct = clamp(jitter(next.system.ramPct, 0.5), 0, 100);
  next.system.wifiDbm = clamp(jitter(next.system.wifiDbm, 1.2), -95, -30);
  next.system.weightLb = clamp(jitter(next.system.weightLb, 0.03), 0, 50);

  // Example: thermals flip sometimes
  if (Math.random() < 0.03) next.health.thermals = next.health.thermals === "OK" ? "WARN" : "OK";

  return next;
}
