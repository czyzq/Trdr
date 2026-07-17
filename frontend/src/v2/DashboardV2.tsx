import React, { useEffect, useState } from "react";
import { apiUrl } from "../api";
import { OverviewPage } from "./OverviewPage";
import { SignalsPage } from "./SignalsPage";
import { BoardPage } from "./BoardPage";
import { TradesPage } from "./TradesPage";
import { StrategyLabPage } from "./StrategyLabPage";
import { SettingsPage } from "./SettingsPage";
import { HomeIcon, PulseIcon, GridIcon, ListIcon, FlaskIcon, GearIcon } from "./icons";

type PageId = "overview" | "signals" | "board" | "trades" | "lab" | "settings";

interface NavItem {
  id: PageId;
  label: string;
  icon: React.FC<{ className?: string }>;
}

const NAV_ITEMS: NavItem[] = [
  { id: "overview", label: "Overview", icon: HomeIcon },
  { id: "signals", label: "Signals", icon: PulseIcon },
  { id: "board", label: "Board", icon: GridIcon },
  { id: "trades", label: "Trades", icon: ListIcon },
  { id: "lab", label: "Strategy Lab", icon: FlaskIcon },
  { id: "settings", label: "Settings", icon: GearIcon },
];

// Bottom bar keeps 5 thumb-reachable tabs; Settings lives in the mobile header.
const MOBILE_TABS = NAV_ITEMS.filter((t) => t.id !== "settings");

const PAGE_TITLES: Record<PageId, string> = {
  overview: "Overview",
  signals: "Signals",
  board: "Indicator Board",
  trades: "Trades",
  lab: "Strategy Lab",
  settings: "Settings",
};

export const DashboardV2: React.FC = () => {
  const [page, setPage] = useState<PageId>(() => {
    const saved = localStorage.getItem("v2_activePage");
    return NAV_ITEMS.some((n) => n.id === saved) ? (saved as PageId) : "overview";
  });
  const [account, setAccount] = useState<any>(null);
  const [connected, setConnected] = useState(true);

  useEffect(() => {
    localStorage.setItem("v2_activePage", page);
  }, [page]);

  // Shared account polling (5s, same cadence as classic)
  useEffect(() => {
    const fetchAccount = async () => {
      try {
        const res = await fetch(apiUrl("account"));
        if (res.ok) {
          setAccount(await res.json());
          setConnected(true);
        } else {
          setConnected(false);
        }
      } catch {
        setConnected(false);
      }
    };
    fetchAccount();
    const interval = setInterval(fetchAccount, 5000);
    return () => clearInterval(interval);
  }, []);

  const renderPage = () => {
    switch (page) {
      case "overview":
        return <OverviewPage account={account} />;
      case "signals":
        return <SignalsPage />;
      case "board":
        return <BoardPage />;
      case "trades":
        return <TradesPage />;
      case "lab":
        return <StrategyLabPage />;
      case "settings":
        return <SettingsPage />;
    }
  };

  return (
    <div className="flex h-[100dvh] w-full bg-[#0b0f17] text-slate-200 antialiased">
      {/* Desktop sidebar: icon rail on md, expanded with labels on lg */}
      <nav
        className="hidden md:flex flex-col flex-shrink-0 border-r border-white/5 bg-[#0d1220] w-16 lg:w-56"
        style={{ paddingTop: "env(safe-area-inset-top, 0px)", paddingBottom: "env(safe-area-inset-bottom, 0px)" }}
      >
        <div className="flex items-center gap-2.5 px-4 lg:px-5 h-16 border-b border-white/5">
          <span className={`w-2 h-2 rounded-full flex-shrink-0 ${connected ? "bg-green-400" : "bg-red-400"}`} />
          <span className="hidden lg:inline text-sm font-bold tracking-widest uppercase text-slate-100">
            Trdr
          </span>
        </div>
        <div className="flex-1 py-3 space-y-1 px-2 lg:px-3">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const active = page === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setPage(item.id)}
                title={item.label}
                className={`w-full flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                  active
                    ? "bg-white/10 text-slate-100"
                    : "text-slate-500 hover:text-slate-300 hover:bg-white/5"
                }`}
              >
                <Icon className="w-5 h-5 flex-shrink-0" />
                <span className="hidden lg:inline">{item.label}</span>
              </button>
            );
          })}
        </div>
        <div className="hidden lg:block px-5 py-4 border-t border-white/5 text-[11px] text-slate-600">
          XAU · XAG · US100 · BTC
        </div>
      </nav>

      {/* Main column */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Mobile header */}
        <header
          className="md:hidden flex items-center justify-between px-4 h-14 flex-shrink-0 border-b border-white/5 bg-[#0d1220]"
          style={{ paddingTop: "env(safe-area-inset-top, 0px)", height: "calc(3.5rem + env(safe-area-inset-top, 0px))" }}
        >
          <div className="flex items-center gap-2.5">
            <span className={`w-2 h-2 rounded-full ${connected ? "bg-green-400" : "bg-red-400"}`} />
            <span className="text-sm font-bold tracking-widest uppercase text-slate-100">Trdr</span>
            <span className="text-xs text-slate-600">/ {PAGE_TITLES[page]}</span>
          </div>
          <button
            onClick={() => setPage("settings")}
            aria-label="Settings"
            className={`p-2 rounded-lg transition-colors ${
              page === "settings" ? "bg-white/10 text-slate-100" : "text-slate-500 hover:text-slate-300"
            }`}
          >
            <GearIcon className="w-5 h-5" />
          </button>
        </header>

        {/* Desktop page title */}
        <header className="hidden md:flex items-center h-16 px-6 flex-shrink-0 border-b border-white/5">
          <h1 className="text-base font-semibold text-slate-100">{PAGE_TITLES[page]}</h1>
        </header>

        {/* Page content */}
        <main
          className="flex-1 overflow-y-auto px-4 py-4 md:px-6 md:py-6"
          style={{
            paddingLeft: "max(1rem, env(safe-area-inset-left, 0px))",
            paddingRight: "max(1rem, env(safe-area-inset-right, 0px))",
          }}
        >
          <div className="max-w-5xl mx-auto pb-4">{renderPage()}</div>
        </main>

        {/* Mobile bottom tab bar */}
        <nav
          className="md:hidden flex items-stretch justify-around flex-shrink-0 border-t border-white/5 bg-[#0d1220]"
          style={{ paddingBottom: "env(safe-area-inset-bottom, 0px)" }}
        >
          {MOBILE_TABS.map((item) => {
            const Icon = item.icon;
            const active = page === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setPage(item.id)}
                className={`flex flex-col items-center justify-center gap-1 py-2.5 min-w-[56px] transition-colors ${
                  active ? "text-slate-100" : "text-slate-600"
                }`}
              >
                <Icon className="w-5 h-5" />
                <span className="text-[10px] font-medium">{item.label.replace("Strategy ", "")}</span>
              </button>
            );
          })}
        </nav>
      </div>
    </div>
  );
};
