import robotImg from "../../assets/robot.png";
import "../../styles/robotPanel.css";

export default function RobotPanel() {
    return (
        <div className="robot-panel">
            <img src={robotImg} alt="Robot" className="robot-img" />
            <h2>ARUA</h2>
            <p>Status: <span className="status-green">Online</span></p>
        </div>
    );
}
