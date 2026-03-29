import "../styles/controlPage.css";

type MoveCmd = "forward" | "backward" | "left" | "right" | "stop";

const BACKEND_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
const DEVICE_ID = "jetson-001";

async function sendMove(cmd: MoveCmd) {
  try {
    const res = await fetch(`${BACKEND_BASE_URL}/device/admin/command`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      credentials: "include",
      body: JSON.stringify({
        device_id: DEVICE_ID,
        command: cmd,
      }),
    });

    if (!res.ok) {
      const text = await res.text();
      throw new Error(`Backend error ${res.status}: ${text}`);
    }

    const data = await res.json();
    console.log("Backend Response:", data);
  } catch (err) {
    console.error("Failed to send command to backend:", err);
  }
}

export default function ControlPage() {
  const onMove = (cmd: MoveCmd) => {
    sendMove(cmd);
  };

  const onStop = () => {
    sendMove("stop");
  };

  return (
    <div className="page">
      <div className="control-header">
        <h1>Robot Control</h1>
        <p className="control-subtitle">Use the D-pad to command the robot.</p>
      </div>

      <div className="control-grid">
        <section className="control-card">
          <h2>Movement</h2>
          <div className="control-divider" />

          <div className="dpad-wrap">
            <div className="dpad">
              <button className="dpad-btn up" onClick={() => onMove("forward")} aria-label="Move forward">
                <span>▲</span>
              </button>

              <button className="dpad-btn left" onClick={() => onMove("left")} aria-label="Move left">
                <span>◀</span>
              </button>

              <button className="stop-btn" onClick={onStop} aria-label="Stop all">
                STOP
              </button>

              <button className="dpad-btn right" onClick={() => onMove("right")} aria-label="Move right">
                <span>▶</span>
              </button>

              <button className="dpad-btn down" onClick={() => onMove("backward")} aria-label="Move backward">
                <span>▼</span>
              </button>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}