import CameraFeedSecure from "../components/UI/CameraFeedSecure";
import "../styles/cameraPage.css";

export default function CameraPage() {
  return (
    <div className="camera-page">
      <h1>Camera Feed</h1>
      <CameraFeedSecure />
    </div>
  );
}
