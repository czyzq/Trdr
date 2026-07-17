import React, { useEffect, useState } from "react";
import { apiUrl } from "../api";
import { Card, SectionLabel, StatTile, DirectionPill, Toggle, EmptyState } from "./ui";
import { fmtUsd, fmtPrice, fmtDateTime, pnlClass } from "./format";

interface Position {
  id: string;
  symbol: string;
  name: string;
  direction: string;
  size: number;
  entry_price: number;
  current_price: number;
  take_profit: number;
  stop_loss: number;
  unrealized_pnl_usd: number;
  opened_at: string;
}

interface OverviewPageProps {
  account: any; // GET /api/account response, polled by DashboardV2
}

export const OverviewPage: React.FC<OverviewPageProps> = ({ account }) => {
  const [positions, setPositions] = useState<Position[]>([]);
  const [todayPnl, setTodayPnl] = useState<number | null>(null);
  const [autoTrade, setAutoTrade] = useState(false);
  const [brokerMode, setBrokerMode] = useState("simulation");
  const [savingAutoTrade, setSavingAutoTrade] = useState(false);
  const [killing, setKilling] = useState(false);

  // Open positions (5s, matches classic cadence)
  useEffect(() => {
    const fetchPositions = async () => {
      try {
        const res = await fetch(apiUrl("trades/open"));
        if (res.ok) {
          const data = await res.json();
          setPositions(data.positions || []);
        }
      } catch {
        /* keep last known */
      }
    };
    fetchPositions();
    const interval = setInterval(fetchPositions, 5000);
    return () => clearInterval(interval);
  }, []);

  // Today's realized P&L from trade history (30s)
  useEffect(() => {
    const fetchToday = async () => {
      try {
        const res = await fetch(apiUrl("trades/history?limit=200"));
        if (!res.ok) return;
        const data = await res.json();
        const today = new Date().toLocaleDateString("en-GB", { timeZone: "Europe/Warsaw" });
        const sum = (data.trades || [])
          .filter((t: any) => {
            if (!t.closed_at) return false;
            const d = new Date(String(t.closed_at).replace("Z", "+00:00"));
            return d.toLocaleDateString("en-GB", { timeZone: "Europe/Warsaw" }) === today;
          })
          .reduce((acc: number, t: any) => acc + (t.pnl_usd || 0), 0);
        setTodayPnl(sum);
      } catch {
        /* keep last known */
      }
    };
    fetchToday();
    const interval = setInterval(fetchToday, 30000);
    return () => clearInterval(interval);
  }, []);

  // Auto-trade state (same endpoint as classic Sidebar)
  useEffect(() => {
    const fetchMode = async () => {
      try {
        const res = await fetch(apiUrl("trading-mode"));
        if (res.ok) {
          const data = await res.json();
          setAutoTrade(Boolean(data.auto_trade));
          setBrokerMode(data.mode || "simulation");
        }
      } catch {
        /* ignore */
      }
    };
    fetchMode();
  }, []);

  const toggleAutoTrade = async (enabled: boolean) => {
    setSavingAutoTrade(true);
    setAutoTrade(enabled);
    try {
      await fetch(`${apiUrl("trading-mode")}?broker=${brokerMode}&autoTrade=${enabled}`, {
        method: "POST",
      });
    } catch {
      setAutoTrade(!enabled); // revert on failure
    } finally {
      setSavingAutoTrade(false);
    }
  };

  const killSwitch = async () => {
    if (!confirm("Engage the optimizer kill switch? This disables the optimizer loop and auto-promotion.")) {
      return;
    }
    setKilling(true);
    try {
      await fetch(apiUrl("optimizer/kill"), { method: "POST" });
    } catch {
      /* best effort */
    } finally {
      setKilling(false);
    }
  };

  const balance = account?.balance_usd;
  const equity = account?.equity_usd;
  const totalPnl = account?.account?.total_pnl_usd;
  const lastScan = account?.account?.last_scan;

  return (
    <div className="space-y-5">
      {/* Stat tiles */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatTile label="Equity" value={fmtUsd(equity)} />
        <StatTile label="Balance" value={fmtUsd(balance)} />
        <StatTile
          label="Today P&L"
          value={fmtUsd(todayPnl, true)}
          valueClass={pnlClass(todayPnl)}
        />
        <StatTile
          label="Total P&L"
          value={fmtUsd(totalPnl, true)}
          valueClass={pnlClass(totalPnl)}
        />
      </div>

      {/* Controls */}
      <Card className="p-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Toggle checked={autoTrade} onChange={toggleAutoTrade} disabled={savingAutoTrade} label="Auto-trade" />
            <div>
              <div className="text-sm font-medium text-slate-200">Auto-trade</div>
              <div className="text-xs text-slate-500">
                Last scan: {lastScan ? fmtDateTime(lastScan) : "–"}
              </div>
            </div>
          </div>
          <button
            onClick={killSwitch}
            disabled={killing}
            className="px-4 py-2 rounded-lg border border-red-400/30 bg-red-400/10 text-red-400 text-sm font-semibold hover:bg-red-400/20 transition-colors disabled:opacity-50"
          >
            {killing ? "Engaging..." : "Kill switch"}
          </button>
        </div>
      </Card>

      {/* Open positions */}
      <div>
        <SectionLabel className="mb-2">
          Open positions ({positions.length})
        </SectionLabel>
        {positions.length === 0 ? (
          <Card>
            <EmptyState title="No open positions" hint="New trades will appear here" />
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {positions.map((pos) => (
              <Card key={pos.id} className="p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <span className="text-sm font-bold text-slate-100">{pos.symbol}</span>
                    <DirectionPill direction={pos.direction} />
                    <span className="text-xs text-slate-500 tabular-nums">×{pos.size}</span>
                  </div>
                  <span className={`text-sm font-bold tabular-nums ${pnlClass(pos.unrealized_pnl_usd)}`}>
                    {fmtUsd(pos.unrealized_pnl_usd, true)}
                  </span>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm tabular-nums">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Entry</span>
                    <span className="text-slate-300">{fmtPrice(pos.entry_price)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Current</span>
                    <span className="text-slate-100">{fmtPrice(pos.current_price)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">TP</span>
                    <span className="text-green-400">{fmtPrice(pos.take_profit)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">SL</span>
                    <span className="text-red-400">{fmtPrice(pos.stop_loss)}</span>
                  </div>
                </div>
                <div className="mt-2 text-xs text-slate-600">
                  Opened {fmtDateTime(pos.opened_at)}
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
