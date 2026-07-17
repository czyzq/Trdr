import React, { useEffect, useState } from "react";
import { apiUrl } from "../api";
import { Card, SectionLabel, DirectionPill, Badge, EmptyState } from "./ui";
import { fmtUsd, fmtPrice, fmtDateTime, pnlClass } from "./format";

interface ClosedTrade {
  id: string;
  symbol: string;
  direction: string;
  size: number;
  entry_price: number;
  exit_price: number;
  pnl_usd: number;
  opened_at: string;
  closed_at: string;
  result: string; // win / loss
  exit_reason?: string; // tp / sl / timeout / manual...
}

const reasonTone = (reason: string): "green" | "red" | "amber" | "slate" => {
  const r = reason.toLowerCase();
  if (r.includes("tp") || r.includes("profit") || r === "win") return "green";
  if (r.includes("sl") || r.includes("stop") || r === "loss") return "red";
  if (r.includes("timeout") || r.includes("time")) return "amber";
  return "slate";
};

export const TradesPage: React.FC = () => {
  const [trades, setTrades] = useState<ClosedTrade[]>([]);
  const [stats, setStats] = useState({ win_count: 0, loss_count: 0, win_rate: 0, total_pnl_usd: 0 });
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const fetchTrades = async () => {
      try {
        const res = await fetch(apiUrl("trades/history?limit=100"));
        if (res.ok) {
          const data = await res.json();
          setTrades(data.trades || []);
          setStats({
            win_count: data.win_count || 0,
            loss_count: data.loss_count || 0,
            win_rate: data.win_rate || 0,
            total_pnl_usd: data.total_pnl_usd || 0,
          });
        }
      } catch {
        /* keep last known */
      } finally {
        setLoaded(true);
      }
    };
    fetchTrades();
    const interval = setInterval(fetchTrades, 15000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-5">
      {/* Stats header */}
      <Card className="p-4">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm tabular-nums">
          <span className="text-slate-400">
            Closed <span className="text-slate-100 font-semibold">{stats.win_count + stats.loss_count}</span>
          </span>
          <span className="text-slate-400">
            Wins <span className="text-green-400 font-semibold">{stats.win_count}</span>
          </span>
          <span className="text-slate-400">
            Losses <span className="text-red-400 font-semibold">{stats.loss_count}</span>
          </span>
          <span className="text-slate-400">
            Win rate <span className={`font-semibold ${stats.win_rate >= 50 ? "text-green-400" : "text-red-400"}`}>{stats.win_rate}%</span>
          </span>
          <span className="ml-auto text-slate-400">
            Total P&L{" "}
            <span className={`font-bold ${pnlClass(stats.total_pnl_usd)}`}>
              {fmtUsd(stats.total_pnl_usd, true)}
            </span>
          </span>
        </div>
      </Card>

      <SectionLabel>Trade history ({trades.length})</SectionLabel>

      {!loaded ? (
        <Card>
          <EmptyState title="Loading trades..." />
        </Card>
      ) : trades.length === 0 ? (
        <Card>
          <EmptyState title="No trade history" hint="Closed trades will appear here" />
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          {trades.map((trade) => {
            const reason = trade.exit_reason || trade.result || "";
            return (
              <Card key={trade.id} className="p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <span className="text-sm font-bold text-slate-100">{trade.symbol}</span>
                    <DirectionPill direction={trade.direction} />
                    {reason && <Badge tone={reasonTone(reason)}>{reason}</Badge>}
                  </div>
                  <span className={`text-sm font-bold tabular-nums ${pnlClass(trade.pnl_usd)}`}>
                    {fmtUsd(trade.pnl_usd, true)}
                  </span>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm tabular-nums">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Entry</span>
                    <span className="text-slate-300">{fmtPrice(trade.entry_price)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Exit</span>
                    <span className="text-slate-300">{fmtPrice(trade.exit_price)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Opened</span>
                    <span className="text-slate-400">{fmtDateTime(trade.opened_at)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Closed</span>
                    <span className="text-slate-400">{fmtDateTime(trade.closed_at)}</span>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
};
