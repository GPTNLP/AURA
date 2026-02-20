// src/services/themeStore.ts

// ===== Theme type =====
export type ThemeOption = "tamu" | "robotic" | "dark" | "light";

// ===== LocalStorage key =====
const THEME_KEY = "aura-theme";

// ===== Load saved theme OR default to TAMU =====
export function loadTheme(): ThemeOption {
  const saved = localStorage.getItem(THEME_KEY) as ThemeOption | null;
  return saved ?? "tamu";
}

// ===== Save theme =====
export function saveTheme(theme: ThemeOption) {
  localStorage.setItem("aura-theme", theme)
}

// ===== Apply theme to HTML root =====
export function applyTheme(theme: ThemeOption) {
  document.documentElement.setAttribute("data-theme", theme);
}
