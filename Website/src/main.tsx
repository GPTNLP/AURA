import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import AppRouter from "./router/AppRouter";
import { AuthProvider } from "./services/authService";
import "./styles/index.css";

// Apply saved theme BEFORE React renders
import { loadTheme, applyTheme } from "./services/themeStore";
import "./styles/index.css";
applyTheme(loadTheme());

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <AppRouter />
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>
);