import React, { useEffect, useState } from "react";
import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../services/authService";

import Layout from "../components/Layout/Layout";

// Login pages
import LoginChooserPage from "../pages/LoginChooserPage";
import LoginAdminPage from "../pages/LoginAdminPage";
import LoginStudentPage from "../pages/LoginStudentPage";
import LoginTAPage from "../pages/LoginTAPage";

// App pages
import DashboardPage from "../pages/DashboardPage";
import CameraPage from "../pages/CameraPage";
import ControlPage from "../pages/ControlPage";
import SettingsPage from "../pages/SettingsPage";
import DatabasePage from "../pages/DatabasePage";
import ChatLogsPage from "../pages/ChatLogsPage";
import SimulatorPage from "../pages/SimulatorPage";
import TAManagePage from "../pages/TAManagePage";
import AdminsPage from "../pages/AdminsPage";

type Role = "admin" | "ta" | "student";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { token, user, refreshMe } = useAuth();
  const location = useLocation();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      if (!token) {
        if (!cancelled) setChecking(false);
        return;
      }

      await refreshMe();

      if (!cancelled) setChecking(false);
    })();

    return () => {
      cancelled = true;
    };
  }, [token, refreshMe]);

  if (!token) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (checking) return null;

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return <>{children}</>;
}

function RequireRole({ allow, children }: { allow: Role[]; children: React.ReactNode }) {
  const { user } = useAuth();

  if (!user) return <Navigate to="/login" replace />;

  const role = user.role as Role;
  if (!allow.includes(role)) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
}

export default function AppRouter() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/login" element={<LoginChooserPage />} />
      <Route path="/login/admin" element={<LoginAdminPage />} />
      <Route path="/login/student" element={<LoginStudentPage />} />
      <Route path="/login/ta" element={<LoginTAPage />} />

      {/* Protected */}
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
        <Route path="settings" element={<SettingsPage />} />

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
          path="admin/ta"
          element={
            <RequireRole allow={["admin"]}>
              <TAManagePage />
            </RequireRole>
          }
        />
        <Route
          path="admin/admins"
          element={
            <RequireRole allow={["admin"]}>
              <AdminsPage />
            </RequireRole>
          }
        />

        {/* Database: Admin + TA */}
        <Route
          path="database"
          element={
            <RequireRole allow={["admin", "ta"]}>
              <DatabasePage />
            </RequireRole>
          }
        />

        <Route path="files" element={<Navigate to="/database" replace />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Route>

      {/* Catch-all */}
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}