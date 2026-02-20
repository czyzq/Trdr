import React, { useState, useEffect } from "react";
import { apiUrl } from "../api";

// Trading Sessions - major market hours in UTC
interface TradingSession {
  name: string;
  city: string;
  openHour: number;
  closeHour: number;
}

const SESSIONS: TradingSession[] = [
  { name: "Sydney", city: "Sydney", openHour: 22, closeHour: 7 },    // 22:00-07:00 UTC
  { name: "Tokyo", city: "Tokyo", openHour: 0, closeHour: 9 },      // 00:00-09:00 UTC  
  { name: "London", city: "London", openHour: 7, closeHour: 16 },   // 07:00-16:00 UTC
  { name: "New York", city: "NewYork", openHour: 14.5, closeHour: 23 }, // 14:30-23:00 UTC
];

function isSessionOpen(session: TradingSession): boolean {
  const now = new Date();
  const utcHour = now.getUTCHours() + now.getUTCMinutes() / 60;
  
  // Handle sessions that span midnight
  if (session.openHour > session.closeHour) {
    return utcHour >= session.openHour || utcHour < session.closeHour;
  }
  return utcHour >= session.openHour && utcHour < session.closeHour;
}

function getSessionStatus(session: TradingSession): { open: boolean; status: string } {
  const now = new Date();
  const utcHour = now.getUTCHours() + now.getUTCMinutes() / 60;
  const open = isSessionOpen(session);
  
  if (open) {
    // Calculate time until close
    let hoursLeft = session.closeHour - utcHour;
    if (hoursLeft < 0) hoursLeft += 24;
    if (hoursLeft >= 0) {
      const h = Math.floor(hoursLeft);
      const m = Math.floor((hoursLeft - h) * 60);
      return { open: true, status: `OTWARTY ${h}h ${m}m` };
    }
  } else {
    // Calculate time until open
    let hoursUntil = session.openHour - utcHour;
    if (hoursUntil < 0) hoursUntil += 24;
    const h = Math.floor(hoursUntil);
    const m = Math.floor((hoursUntil - h) * 60);
    return { open: false, status: `za ${h}h ${m}m` };
  }
  return { open, status: open ? "OTWARTY" : "ZAMKNIĘTY" };
}

const MarketStatus: React.FC = () => {
  const [time, setTime] = useState({ utc: "", warsaw: "" });
  
  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTime({
        utc: now.toLocaleTimeString("en-GB", { timeZone: "UTC", hour: "2-digit", minute: "2-digit" }),
        warsaw: now.toLocaleTimeString("en-GB", { timeZone: "Europe/Warsaw", hour: "2-digit", minute: "2-digit" }),
      });
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="p-2 rounded-sm" style={{ backgroundColor: "#0b0f1a" }}>
      <div className="text-[10px] mb-2" style={{ color: "#6b7280" }}>
        SESJE • {time.warsaw} ({time.utc} UTC)
      </div>
      <div className="space-y-1">
        {SESSIONS.map((s) => {
          const { open, status } = getSessionStatus(s);
          return (
            <div key={s.name} className="flex items-center justify-between text-[10px]">
              <div className="flex items-center gap-1.5">
                <div
                  className="w-1.5 h-1.5 rounded-full"
                  style={{ backgroundColor: open ? "#22c55e" : "#ef4444" }}
                />
                <span style={{ color: "#e5e7eb" }}>{s.name}</span>
              </div>
              <span style={{ color: open ? "#22c55e" : "#9ca3af" }}>
                {status}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

interface SidebarProps {
  accountData?: any;
}

export const Sidebar: React.FC<SidebarProps> = ({ accountData }) => {
  const [lastScan, setLastScan] = useState("--");
  const [isScanning, setIsScanning] = useState(false);

  const balance = accountData?.balance_usd ?? 0;
  const equity = accountData?.equity_usd ?? 0;
  const openTrades = accountData?.open_trades ?? 0;
  const closedTrades = accountData?.closed_trades ?? 0;
  const winRate = accountData?.win_rate ?? 0;
  const totalPnl = accountData?.total_pnl_usd ?? 0;
  const mode = accountData?.mode ?? "simulate";

  useEffect(() => {
    const updateScan = () => {
      if (accountData?.last_scan) {
        const scanTime = new Date(accountData.last_scan);
        const now = new Date();
        const diffSecs = Math.floor(
          (now.getTime() - scanTime.getTime()) / 1000,
        );
        if (diffSecs < 5) setLastScan("Now");
        else if (diffSecs < 60) setLastScan(`${diffSecs}s ago`);
        else if (diffSecs < 3600)
          setLastScan(`${Math.floor(diffSecs / 60)}m ago`);
        else setLastScan(`${Math.floor(diffSecs / 3600)}h ago`);
      }
    };
    updateScan();
    const interval = setInterval(updateScan, 1000);
    return () => clearInterval(interval);
  }, [accountData]);

  const toggleMode = async () => {
    const newMode = mode === "simulate" ? "live" : "simulate";
    try {
      await fetch(`${apiUrl("account/mode")}?mode=${newMode}`, {
        method: "POST",
      });
    } catch (error) {
      console.error("Failed to toggle mode:", error);
    }
  };

  const resetAccount = async () => {
    try {
      await fetch(apiUrl("account/reset"), { method: "POST" });
    } catch (error) {
      console.error("Failed to reset account:", error);
    }
  };

  const pnlColor = totalPnl >= 0 ? "#22c55e" : "#ef4444";
  // Use initial_balance from account if available, fallback to calculating from equity - balance
  const initialBalance = accountData?.initial_balance_usd ?? equity - totalPnl;
  const equityChange = totalPnl; // Total P&L is the equity change from initial
  const equityChangePct =
    initialBalance > 0 ? (equityChange / initialBalance) * 100 : 0;

  return (
    <div
      className="w-60 h-full flex flex-col overflow-y-auto"
      style={{ backgroundColor: "#0d1220", borderRight: "1px solid #1a1f35" }}
    >
      {/* Balance Section */}
      <div className="p-4" style={{ borderBottom: "1px solid #1a1f35" }}>
        <div
          className="text-[10px] uppercase tracking-widest mb-1.5"
          style={{ color: "#4a5568" }}
        >
          Balance
        </div>
        <div className="text-lg font-bold mb-0.5" style={{ color: "#e2e8f0" }}>
          ${balance.toLocaleString("en-US", { minimumFractionDigits: 2 })}{" "}
          <span className="text-xs font-normal" style={{ color: "#64748b" }}>
            USD
          </span>
        </div>
      </div>

      {/* Equity Section */}
      <div className="p-4" style={{ borderBottom: "1px solid #1a1f35" }}>
        <div
          className="text-[10px] uppercase tracking-widest mb-1.5"
          style={{ color: "#4a5568" }}
        >
          Equity
        </div>
        <div className="text-base font-bold" style={{ color: "#e2e8f0" }}>
          ${equity.toLocaleString("en-US", { minimumFractionDigits: 2 })}{" "}
          <span
            className="text-[10px] font-normal"
            style={{ color: "#64748b" }}
          >
            USD
          </span>
        </div>
        <div className="flex items-center gap-1.5 mt-1">
          <span className="text-[11px] font-medium" style={{ color: pnlColor }}>
            {equityChange >= 0 ? "+" : ""}${equityChange.toFixed(2)} USD
          </span>
          <span className="text-[10px]" style={{ color: pnlColor }}>
            ({equityChangePct >= 0 ? "+" : ""}
            {equityChangePct.toFixed(2)}%)
          </span>
        </div>
      </div>

      {/* Stats Grid */}
      <div
        className="p-4 grid grid-cols-2 gap-3"
        style={{ borderBottom: "1px solid #1a1f35" }}
      >
        <StatBox label="Open" value={openTrades.toString()} color="#3b82f6" />
        <StatBox
          label="Closed"
          value={closedTrades.toString()}
          color="#64748b"
        />
        <StatBox
          label="Win Rate"
          value={`${winRate}%`}
          color={
            winRate >= 50 ? "#22c55e" : winRate > 0 ? "#ef4444" : "#64748b"
          }
        />
        <StatBox
          label="Total P&L"
          value={`${totalPnl >= 0 ? "+" : ""}${totalPnl.toFixed(0)}`}
          color={pnlColor}
        />
      </div>

      {/* Mode Toggle */}
      <div className="p-4" style={{ borderBottom: "1px solid #1a1f35" }}>
        <div
          className="text-[10px] uppercase tracking-widest mb-2"
          style={{ color: "#4a5568" }}
        >
          Trading Mode
        </div>
        <button
          onClick={toggleMode}
          className="w-full text-[11px] font-bold py-2 rounded-sm border transition-all"
          style={{
            backgroundColor:
              mode === "simulate"
                ? "rgba(234, 179, 8, 0.08)"
                : "rgba(239, 68, 68, 0.08)",
            borderColor:
              mode === "simulate"
                ? "rgba(234, 179, 8, 0.3)"
                : "rgba(239, 68, 68, 0.3)",
            color: mode === "simulate" ? "#eab308" : "#ef4444",
          }}
        >
          {mode === "simulate" ? "SIMULATION MODE" : "LIVE MODE"}
        </button>
        <div
          className="text-[9px] mt-1.5 text-center"
          style={{ color: "#374151" }}
        >
          {mode === "simulate"
            ? "Paper trading with virtual USD"
            : "Real trading - use caution"}
        </div>
      </div>

      {/* Instruments
      <div className="p-4" style={{ borderBottom: '1px solid #1a1f35' }}>
        <div className="text-[10px] uppercase tracking-widest mb-2.5" style={{ color: '#4a5568' }}>
          Instruments
        </div>
        <div className="space-y-1.5">
          {[
            { symbol: 'XAU', name: 'Gold', color: '#eab308' },
            { symbol: 'XAG', name: 'Silver', color: '#94a3b8' },
            { symbol: 'US100', name: 'Nasdaq', color: '#3b82f6' },
            { symbol: 'BTC', name: 'Bitcoin', color: '#f97316' },
          ].map((inst) => (
            <div key={inst.symbol} className="flex items-center justify-between py-1">
              <div className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: inst.color }} />
                <span className="text-[11px] font-medium" style={{ color: '#c8cdd8' }}>
                  {inst.symbol}
                </span>
              </div>
              <span className="text-[10px]" style={{ color: '#4a5568' }}>
                {inst.name}
              </span>
            </div>
          ))}
        </div>
      </div> */}

      {/* Market Status - replaces Scanner/Last scan */}
      <div className="p-3" style={{ borderBottom: "1px solid #1a1f35" }}>
        <MarketStatus />
      </div>

      {/* Scanner Status - replaced by MarketStatus */}
      {/*
      <div className="p-4" style={{ borderBottom: "1px solid #1a1f35" }}>
        <div className="flex items-center justify-between mb-2">
          <div
            className="text-[10px] uppercase tracking-widest"
            style={{ color: "#4a5568" }}
          >
            Scanner
          </div>
          <div className="flex items-center gap-1.5">
            <div
              className={`w-1.5 h-1.5 rounded-full ${isScanning ? "animate-pulse" : ""}`}
              style={{ backgroundColor: "#22c55e" }}
            />
            <span className="text-[10px]" style={{ color: "#22c55e" }}>
              Active
            </span>
          </div>
        </div>
      </div>
      */}

      {/* Reset Button */}
      <div className="p-4 mt-auto">
        <button
          onClick={resetAccount}
          className="w-full text-[10px] py-1.5 rounded-sm border transition-all hover:bg-opacity-10"
          style={{
            borderColor: "#1a1f35",
            color: "#4a5568",
          }}
        >
          Reset Account
        </button>
      </div>
    </div>
  );
};

const StatBox: React.FC<{ label: string; value: string; color: string }> = ({
  label,
  value,
  color,
}) => (
  <div className="p-2.5 rounded-sm" style={{ backgroundColor: "#0b0f1a" }}>
    <div
      className="text-[9px] uppercase tracking-widest mb-1"
      style={{ color: "#4a5568" }}
    >
      {label}
    </div>
    <div className="text-sm font-bold" style={{ color }}>
      {value}
    </div>
  </div>
);
