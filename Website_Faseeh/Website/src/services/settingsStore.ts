export type ThemeOption = "tamu" | "robotic" | "dark" | "light";
export type UIProfile = "auto" | "desktop";
export type DashboardLayout = "control" | "engineering" | "discord" | "tars";

export interface SettingsData {
    theme: ThemeOption;
    dashboardLayout: DashboardLayout; // layout for desktop
}

const DEFAULT_SETTINGS: SettingsData = {
    theme: "tamu",
    dashboardLayout: "control",    // Desktop default
};

export function loadSettings(): SettingsData {
    try {
        const saved = localStorage.getItem("arua-settings");
        return saved ? JSON.parse(saved) : DEFAULT_SETTINGS;
    } catch {
        return DEFAULT_SETTINGS;
    }
}

export function saveSettings(data: SettingsData) {
    localStorage.setItem("arua-settings", JSON.stringify(data));
}

export function resetSettings() {
    localStorage.setItem("arua-settings", JSON.stringify(DEFAULT_SETTINGS));
}
