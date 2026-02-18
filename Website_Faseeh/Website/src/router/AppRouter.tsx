// src/router/AppRouter.tsx
import { Routes, Route, Navigate } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuth } from "../services/authService";

// Pages / Layout
import Layout from "../components/Layout/Layout";
import DashboardPage from "../pages/DashboardPage";
import ControlPage from "../pages/ControlPage";
import ChatPage from "../pages/ChatPage";
import CameraPage from "../pages/CameraPage";
import SettingsPage from "../pages/SettingsPage";
import LoginPage from "../pages/LoginPage";

function ProtectedRoute({ children }: { children: ReactNode }) {
    const { user } = useAuth();
    if (!user) return <Navigate to="/login" replace />;
    return <>{children}</>;
}

export default function AppRouter() {
    return (
        <Routes>
            {/* Public */}
            <Route path="/login" element={<LoginPage />} />

            {/* Protected App */}
            <Route
                path="/"
                element={
                    <ProtectedRoute>
                        <Layout />
                    </ProtectedRoute>
                }
            >
                <Route index element={<DashboardPage />} />
                <Route path="control" element={<ControlPage />} />
                <Route path="chat" element={<ChatPage />} />
                <Route path="camera" element={<CameraPage />} />
                <Route path="settings" element={<SettingsPage />} />
            </Route>

            {/* Fallback */}
            <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
    );
}
