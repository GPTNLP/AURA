import React, { useEffect } from "react";
import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../services/authService";

import LoginPage from "../pages/LoginPage";
import DashboardPage from "../pages/DashboardPage";
import CameraPage from "../pages/CameraPage";
import ControlPage from "../pages/ControlPage";
import SettingsPage from "../pages/SettingsPage";

import FilesPage from "../pages/FilesPage";
import ChatLogsPage from "../pages/ChatLogsPage";
import BotPage from "../pages/BotPage";

import Layout from "../components/Layout/Layout";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { token, refreshMe } = useAuth();
  const location = useLocation();

  // try to restore user if token exists
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
      <Route path="/login" element={<LoginPage />} />

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
        <Route path="settings" element={<SettingsPage />} />

        <Route path="files" element={<FilesPage />} />
        <Route path="bot" element={<BotPage />} />
        <Route path="logs" element={<ChatLogsPage />} />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}