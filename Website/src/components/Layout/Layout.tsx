import { Outlet } from "react-router-dom";
import Navbar from "./Navbar";
import Sidebar from "./Sidebar";
import "../../styles/layout.css";

export default function Layout() {
  return (
    <div className="layout-wrapper">
      <Sidebar />

      <div className="layout-content">
        <Navbar />

        <main className="layout-main">
          {/* If you don't see this, Outlet is not the issue */}
          {/* <div style={{ padding: 12 }}>Outlet mounted ✅</div> */}

          <Outlet />
        </main>
      </div>
    </div>
  );
}