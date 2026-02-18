// src/components/Layout/Layout.tsx
import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";
import Navbar from "./Navbar";
import "../../styles/layout.css";

export default function Layout() {
    return (
        <div className="layout-wrapper">
            <Sidebar />

            <div className="layout-content">
                <Navbar />
                <main className="layout-main">
                    <Outlet />
                </main>
            </div>
        </div>
    );
}
