import ThemeSelector from "../components/UI/ThemeSelector";
import "../styles/settings.css";

export default function SettingsPage() {
    return (
        <div className="settings-container">
            <h2>Settings</h2>

            <div className="settings-section">
                <h3>Appearance</h3>
                <ThemeSelector />
            </div>

            <div className="settings-section">
                <h3>System Preferences</h3>
                <p>Additional options coming soon…</p>
            </div>
        </div>
    );
}
