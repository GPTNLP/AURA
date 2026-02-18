// src/components/UI/ThemeSelector.tsx
import { useEffect, useState } from "react";
import { loadTheme, saveTheme, applyTheme } from "../../services/themeStore";
import type { ThemeOption } from "../../services/themeStore";

export default function ThemeSelector() {
  const [theme, setTheme] = useState<ThemeOption>(() => loadTheme());

  useEffect(() => {
    applyTheme(theme);
    saveTheme(theme);
  }, [theme]);

  return (
    <div className="theme-selector">
      <label htmlFor="theme-select">Color Theme</label>

      <div className="theme-row">
        <span className="theme-dot" aria-hidden />
        <select
          id="theme-select"
          value={theme}
          onChange={(e) => setTheme(e.target.value as ThemeOption)}
        >
          <option value="tamu">TAMU (Maroon)</option>
          <option value="robotic">Robotic</option>
          <option value="dark">Dark</option>
          <option value="light">Light</option>
        </select>
      </div>
    </div>
  );
}
