import React from "react";
import ReactDOM from "react-dom/client";
import { Dashboard } from "./components/Dashboard";
import { DashboardV2 } from "./v2/DashboardV2";
import { TokenGate } from "./TokenGate";
import { getUiVersion } from "./uiVersion";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <TokenGate>{getUiVersion() === "classic" ? <Dashboard /> : <DashboardV2 />}</TokenGate>
  </React.StrictMode>,
);
