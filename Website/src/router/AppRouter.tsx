import React, { useEffect } from "react";
import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../services/authService";

import LoginPage from "../pages/LoginPage";
import DashboardPage from "../pages/DashboardPage";
import CameraPage from "../pages/CameraPage";
import ControlPage from "../pages/ControlPage";
import SettingsPage from "../pages/SettingsPage";

import DatabasePage from "../pages/DatabasePage";
import ChatLogsPage from "../pages/ChatLogsPage";
import SimulatorPage from "../pages/SimulatorPage";

import Layout from "../components/Layout/Layout";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { token, refreshMe } = useAuth();
  const location = useLocation();

  useEffect(() => {
    if (token) refreshMe();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  if (!token) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <>{children}</>;
}

export default function AppRouter() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/login" element={<LoginPage />} />

      {/* Protected */}
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="control" element={<ControlPage />} />
        <Route path="camera" element={<CameraPage />} />

        {/* ✅ Simulator = chat */}
        <Route path="simulator" element={<SimulatorPage />} />

        {/* ✅ Database page is canonical */}
        <Route path="database" element={<DatabasePage />} />

        {/* ✅ Old route still works */}
        <Route path="files" element={<Navigate to="/database" replace />} />

        <Route path="logs" element={<ChatLogsPage />} />
        <Route path="settings" element={<SettingsPage />} />

        {/* Protected catch-all */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>

      {/* Global catch-all */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}