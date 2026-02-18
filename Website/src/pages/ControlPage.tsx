import "../styles/controlPage.css";

type MoveCmd = "forward" | "backward" | "left" | "right";

// TODO: replace these with your actual backend/service calls
function sendMove(cmd: MoveCmd) {
  console.log("MOVE:", cmd);
}

function stopAll() {
  console.log("STOP ALL");
}

export default function ControlPage() {
  const onMove = (cmd: MoveCmd) => {
    sendMove(cmd);
  };

  const onStop = () => {
    stopAll();
  };

  return (
    <div className="page">
      <div className="control-header">
        <h1>Robot Control</h1>
        <p className="control-subtitle">Use the D-pad or WASD. Space = Stop.</p>
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

          <div className="control-hint">Tip: WASD to move, Space to stop.</div>
        </section>

        <section className="control-card">
          <h2>Actions</h2>
          <div className="control-divider" />

          <div className="actions-list">
            <button className="action-btn" onClick={() => console.log("Mode: Manual")}>Mode: Manual</button>
            <button className="action-btn" onClick={() => console.log("Mode: Auto")}>Mode: Auto</button>
            <button className="action-btn" onClick={() => console.log("Reset")}>Reset System</button>
          </div>
        </section>
      </div>
    </div>
  );
}
