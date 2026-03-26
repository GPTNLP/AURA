import React from "react";
import "../styles/controlPage.css";

type MoveCmd = "forward" | "backward" | "left" | "right" | "stop";

// Point this to your Jetson's local IP address and Flask port
const JETSON_API_URL = "http://<YOUR_JETSON_IP>:5001/move"; 

function sendMove(cmd: MoveCmd) {
  fetch(JETSON_API_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ cmd }),
  })
    .then((res) => res.json())
    .then((data) => console.log("Jetson Response:", data))
    .catch((err) => console.error("Failed to send command to Jetson:", err));
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
        <p className="control-subtitle">Use the D-pad to command the Jetson.</p>
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