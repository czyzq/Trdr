import React from "react";
import ReactDOM from "react-dom/client";
import { Dashboard } from "./components/Dashboard";
import { DashboardV2 } from "./v2/DashboardV2";
import { getUiVersion } from "./uiVersion";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {getUiVersion() === "classic" ? <Dashboard /> : <DashboardV2 />}
  </React.StrictMode>,
);
