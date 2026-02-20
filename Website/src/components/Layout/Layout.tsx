import React from "react";
import Navbar from "./Navbar";
import Sidebar from "./Sidebar";
import "../../styles/layout.css";

export default function Layout({ children }: { children?: React.ReactNode }) {
  return (
    <div className="layout-wrapper">
      <Sidebar />

      <div className="layout-content">
        <Navbar />
        <main className="layout-main">{children}</main>
      </div>
    </div>
  );
}