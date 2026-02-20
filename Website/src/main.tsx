import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { MsalProvider } from "@azure/msal-react";

import AppRouter from "./router/AppRouter";
import { AuthProvider } from "./services/authService";
import { msalInstance } from "./msal";
import { loadTheme, applyTheme } from "./services/themeStore";
import "./styles/index.css";

// Apply saved theme BEFORE React renders
applyTheme(loadTheme());

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <MsalProvider instance={msalInstance}>
      <AuthProvider>
        <BrowserRouter>
          <AppRouter />
        </BrowserRouter>
      </AuthProvider>
    </MsalProvider>
  </React.StrictMode>
);