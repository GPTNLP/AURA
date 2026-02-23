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
import TAManagerPage from "../pages/TAManagerPage";

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

function RequireRole({
  allow,
  children,
}: {
  allow: Array<"admin" | "ta" | "student">;
  children: React.ReactNode;
}) {
  const { user } = useAuth();
  if (!user) return null;
  if (!allow.includes(user.role)) return <Navigate to="/dashboard" replace />;
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
        {/* Everyone */}
        <Route index element={<DashboardPage />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="camera" element={<CameraPage />} />
        <Route path="simulator" element={<SimulatorPage />} />

        {/* Admin-only */}
        <Route
          path="control"
          element={
            <RequireRole allow={["admin"]}>
              <ControlPage />
            </RequireRole>
          }
        />
        <Route
          path="logs"
          element={
            <RequireRole allow={["admin"]}>
              <ChatLogsPage />
            </RequireRole>
          }
        />
        <Route
          path="settings"
          element={
            <RequireRole allow={["admin"]}>
              <SettingsPage />
            </RequireRole>
          }
        />
        <Route
          path="admin/ta"
          element={
            <RequireRole allow={["admin"]}>
              <TAManagerPage />
            </RequireRole>
          }
        />

        {/* Admin + TA */}
        <Route
          path="database"
          element={
            <RequireRole allow={["admin", "ta"]}>
              <DatabasePage />
            </RequireRole>
          }
        />

        {/* Old route still works (admin + TA because it's database) */}
        <Route
          path="files"
          element={
            <RequireRole allow={["admin", "ta"]}>
              <Navigate to="/database" replace />
            </RequireRole>
          }
        />

        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}