import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "../services/authService";

import LoginPage from "../pages/LoginPage";
import DashboardPage from "../pages/DashboardPage";
import CameraPage from "../pages/CameraPage";
import ControlPage from "../pages/ControlPage";
import SettingsPage from "../pages/SettingsPage";
import Admin from "../pages/admin";
import StudentPortal from "../pages/StudentPortal";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { token } = useAuth();
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function AdminRoute({ children }: { children: React.ReactNode }) {
  const { token, user } = useAuth();
  if (!token) return <Navigate to="/login" replace />;
  if (user?.role !== "admin") return <Navigate to="/" replace />;
  return <>{children}</>;
}

export default function AppRouter() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/student-portal" element={<StudentPortal />} />

      {/* Protected */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/camera"
        element={
          <ProtectedRoute>
            <CameraPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/control"
        element={
          <ProtectedRoute>
            <ControlPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/settings"
        element={
          <ProtectedRoute>
            <SettingsPage />
          </ProtectedRoute>
        }
      />

      {/* Admin-only */}
      <Route
        path="/ml-admin"
        element={
          <AdminRoute>
            <Admin />
          </AdminRoute>
        }
      />

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
