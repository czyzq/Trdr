import React, { useEffect, useState } from "react";
import { apiUrl } from "../api";
import { Card, SectionLabel, DirectionPill, SymbolChips, EmptyState, ScoreBar } from "./ui";
import { fmtPrice, fmtDateTime } from "./format";

interface SignalComponent {
  type: string;
  name: string;
  value: number;
  description: string;
  confidence: number;
}

interface Signal {
  symbol: string;
  direction: string;
  score: number;
  confidence: number;
  technical_score: number;
  price_action_score: number;
  news_score: number;
  components: SignalComponent[];
  current_price: number;
  time_horizon: string;
  timestamp: string;
}

const ALL = "ALL";

export const SignalsPage: React.FC = () => {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [selected, setSelected] = useState<string>(ALL);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const fetchSignals = async () => {
      try {
        const res = await fetch(apiUrl("signals"));
        if (res.ok) {
          const data = await res.json();
          setSignals(data.signals || []);
        }
      } catch {
        /* keep last known */
      } finally {
        setLoaded(true);
      }
    };
    fetchSignals();
    const interval = setInterval(fetchSignals, 30000); // 30s
    return () => clearInterval(interval);
  }, []);

  const symbols = Array.from(new Set(signals.map((s) => s.symbol)));
  const visible = selected === ALL ? signals : signals.filter((s) => s.symbol === selected);

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <SectionLabel>Composite signals</SectionLabel>
        <SymbolChips symbols={[ALL, ...symbols]} selected={selected} onSelect={setSelected} />
      </div>

      {!loaded ? (
        <Card>
          <EmptyState title="Loading signals..." />
        </Card>
      ) : visible.length === 0 ? (
        <Card>
          <EmptyState title="No signals available" hint="Signals refresh every 30 seconds" />
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          {visible.map((sig) => (
            <Card key={sig.symbol} className="p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <span className="text-base font-bold text-slate-100">{sig.symbol}</span>
                  <DirectionPill direction={sig.direction} />
                </div>
                <div className="text-sm text-slate-300 tabular-nums">{fmtPrice(sig.current_price)}</div>
              </div>

              <div className="mt-4">
                <div className="flex items-center justify-between text-xs text-slate-500 mb-1.5">
                  <span>Sell</span>
                  <span className="tabular-nums text-slate-300 font-semibold">
                    Score {sig.score >= 0 ? "+" : ""}{sig.score.toFixed(2)}
                  </span>
                  <span>Buy</span>
                </div>
                <ScoreBar score={sig.score} />
                <div className="mt-1.5 text-xs text-slate-500">
                  Confidence <span className="text-slate-300 tabular-nums">{Math.round(sig.confidence * 100)}%</span>
                  <span className="mx-1.5 text-slate-700">·</span>
                  Horizon <span className="text-slate-300">{sig.time_horizon}</span>
                </div>
              </div>

              {sig.components && sig.components.length > 0 && (
                <div className="mt-4">
                  <SectionLabel className="mb-2">Breakdown</SectionLabel>
                  <div className="flex flex-wrap gap-1.5">
                    {sig.components.map((c, i) => (
                      <span
                        key={c.name + i}
                        title={c.description}
                        className={`px-2 py-1 rounded-md border text-[11px] font-medium tabular-nums ${
                          c.value > 0.05
                            ? "text-green-400 bg-green-400/10 border-green-400/20"
                            : c.value < -0.05
                              ? "text-red-400 bg-red-400/10 border-red-400/20"
                              : "text-slate-400 bg-slate-400/10 border-slate-400/20"
                        }`}
                      >
                        {c.name} {c.value >= 0 ? "+" : ""}{c.value.toFixed(2)}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div className="mt-3 text-xs text-slate-600">
                Updated {fmtDateTime(sig.timestamp)}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};
