import React, { useState } from "react";
import { Card, SectionLabel, SymbolChips, EmptyState } from "./ui";
import { useBoard } from "./useBoard";

const SYMBOLS = ["XAU", "XAG", "US100", "BTC"];

const voteClass = (vote: string) => {
  if (vote === "buy") return "bg-green-400";
  if (vote === "sell") return "bg-red-400";
  return "bg-slate-500";
};

export const BoardPage: React.FC = () => {
  const [symbol, setSymbol] = useState<string>(() => {
    return localStorage.getItem("cfd_selectedSymbol") || "XAU";
  });
  const { board, error, loading, refresh } = useBoard(symbol);

  const selectSymbol = (s: string) => {
    setSymbol(s);
    localStorage.setItem("cfd_selectedSymbol", s);
  };

  const timeframes = board ? Array.from(new Set(board.rows.map((r) => r.timeframe))) : [];

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <SymbolChips symbols={SYMBOLS} selected={symbol} onSelect={selectSymbol} />
        <button
          onClick={refresh}
          disabled={loading}
          className="px-3 py-1.5 rounded-lg border border-white/10 text-sm text-slate-300 hover:bg-white/5 transition-colors disabled:opacity-50"
        >
          {loading ? "Loading..." : "Refresh"}
        </button>
      </div>

      {/* Consensus header */}
      {board && (
        <Card className="p-4">
          <SectionLabel className="mb-2">Consensus — {board.symbol}</SectionLabel>
          <div className="flex items-center gap-5 text-sm tabular-nums">
            <span className="text-green-400 font-semibold">{board.consensus.buy} buy</span>
            <span className="text-red-400 font-semibold">{board.consensus.sell} sell</span>
            <span className="text-slate-400 font-semibold">{board.consensus.neutral} neutral</span>
          </div>
        </Card>
      )}

      {error ? (
        <Card>
          <EmptyState title={error} />
        </Card>
      ) : !board ? (
        <Card>
          <EmptyState title="Loading indicator board..." />
        </Card>
      ) : (
        <div className="space-y-5">
          {timeframes.map((tf) => (
            <div key={tf}>
              <SectionLabel className="mb-2">{tf}</SectionLabel>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
                {board.rows
                  .filter((r) => r.timeframe === tf)
                  .map((row) => (
                    <Card
                      key={tf + row.name}
                      className="flex items-center gap-2.5 px-3 py-2.5"
                    >
                      <span
                        className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${voteClass(row.vote)}`}
                        style={{ opacity: 0.4 + 0.6 * Math.min(1, row.strength) }}
                        title={
                          row.value !== null
                            ? `${row.name}: ${row.value.toFixed(4)} (norm ${
                                row.normalized !== null ? row.normalized.toFixed(2) : "n/a"
                              })`
                            : `${row.name}: no data`
                        }
                      />
                      <span className="text-sm text-slate-200 truncate">{row.name}</span>
                    </Card>
                  ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
