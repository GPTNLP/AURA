import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
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
  const { token } = useAuth();
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

/**
 * role="student" means: student OR admin can access
 * role="admin" means: admin only
 */
function RequireRole({
  role,
  children,
}: {
  role: "admin" | "student";
  children: React.ReactNode;
}) {
  const { token, user } = useAuth();

  if (!token) return <Navigate to="/login" replace />;

  const userRole = user?.role;

  if (role === "student") {
    if (userRole !== "student" && userRole !== "admin") {
      return <Navigate to="/" replace />;
    }
    return <>{children}</>;
  }

  // admin-only
  if (userRole !== "admin") return <Navigate to="/" replace />;
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
        {/* shared pages */}
        <Route index element={<DashboardPage />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="control" element={<ControlPage />} />
        <Route path="camera" element={<CameraPage />} />
        <Route path="settings" element={<SettingsPage />} />

        {/* shared pages (student + admin) */}
        <Route
          path="files"
          element={
            <RequireRole role="student">
              <FilesPage />
            </RequireRole>
          }
        />
        <Route
          path="bot"
          element={
            <RequireRole role="student">
              <BotPage />
            </RequireRole>
          }
        />

        {/* admin-only */}
        <Route
          path="logs"
          element={
            <RequireRole role="admin">
              <ChatLogsPage />
            </RequireRole>
          }
        />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}