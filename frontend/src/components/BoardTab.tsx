import React, { useState, useEffect, useCallback } from "react";
import { apiUrl } from "../api";

interface BoardRow {
  name: string;
  timeframe: string;
  value: number | null;
  normalized: number | null;
  vote: "buy" | "sell" | "neutral";
  strength: number;
}

interface BoardResponse {
  symbol: string;
  rows: BoardRow[];
  consensus: { buy: number; sell: number; neutral: number };
  generated_at: string;
}

const voteColor = (vote: string) => {
  if (vote === "buy") return "var(--success)";
  if (vote === "sell") return "var(--danger)";
  return "var(--text-muted)";
};

interface BoardTabProps {
  symbol: string;
}

export const BoardTab: React.FC<BoardTabProps> = ({ symbol }) => {
  const [board, setBoard] = useState<BoardResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchBoard = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch(apiUrl("signals/board?symbol=" + symbol));
      const data = await response.json();
      if (response.ok) {
        setBoard(data);
        setError(null);
      } else {
        setBoard(null);
        setError(data.error || "Failed to load board");
      }
    } catch (e) {
      setError("Failed to fetch indicator board");
    } finally {
      setLoading(false);
    }
  }, [symbol]);

  useEffect(() => {
    fetchBoard();
    const interval = setInterval(fetchBoard, 30000); // 30s
    return () => clearInterval(interval);
  }, [fetchBoard]);

  const timeframes = board
    ? Array.from(new Set(board.rows.map((r) => r.timeframe)))
    : [];

  return (
    <div className="h-full flex flex-col p-2 md:p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <span
          className="text-[11px] font-medium uppercase tracking-wider"
          style={{ color: "var(--text-muted)" }}
        >
          Indicator Board — {symbol}
        </span>
        <div className="flex items-center gap-3">
          {board && (
            <span className="text-[11px] font-bold">
              <span style={{ color: "var(--success)" }}>
                {board.consensus.buy} buy
              </span>
              <span style={{ color: "#4a5568" }}> / </span>
              <span style={{ color: "var(--danger)" }}>
                {board.consensus.sell} sell
              </span>
              <span style={{ color: "#4a5568" }}> / </span>
              <span style={{ color: "var(--text-muted)" }}>
                {board.consensus.neutral} neutral
              </span>
            </span>
          )}
          <button
            onClick={() => fetchBoard()}
            disabled={loading}
            className="px-3 py-1 text-xs bg-[var(--bg-tertiary)]/50 hover:bg-blue-500/70 rounded border border-[var(--border-light)]/50 text-[var(--text-primary)] transition-all font-medium"
          >
            {loading ? "Loading..." : "Refresh"}
          </button>
        </div>
      </div>

      {/* Content */}
      <div
        className="flex-1 overflow-auto rounded-sm p-3"
        style={{
          backgroundColor: "var(--bg-secondary)",
          border: "1px solid var(--bg-tertiary)",
        }}
      >
        {error ? (
          <div
            className="h-full flex items-center justify-center"
            style={{ color: "var(--danger)" }}
          >
            <div className="text-xs uppercase tracking-widest">{error}</div>
          </div>
        ) : !board ? (
          <div
            className="h-full flex items-center justify-center"
            style={{ color: "#4a5568" }}
          >
            <div className="text-xs uppercase tracking-widest">
              Loading indicator board...
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {timeframes.map((tf) => (
              <div key={tf}>
                <div
                  className="text-[10px] font-medium uppercase tracking-wider mb-2"
                  style={{ color: "#4a5568" }}
                >
                  {tf}
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
                  {board.rows
                    .filter((r) => r.timeframe === tf)
                    .map((row) => (
                      <div
                        key={tf + row.name}
                        className="flex items-center gap-2 rounded-sm px-2.5 py-2"
                        style={{
                          backgroundColor: "var(--bg-primary)",
                          border: "1px solid #131825",
                        }}
                        title={
                          row.value !== null
                            ? `${row.name}: ${row.value.toFixed(4)} (norm ${
                                row.normalized !== null
                                  ? row.normalized.toFixed(2)
                                  : "n/a"
                              })`
                            : `${row.name}: no data`
                        }
                      >
                        <div
                          className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                          style={{
                            backgroundColor: voteColor(row.vote),
                            opacity: 0.4 + 0.6 * Math.min(1, row.strength),
                          }}
                        />
                        <span
                          className="text-[10px] font-medium truncate"
                          style={{ color: "var(--text-primary)" }}
                        >
                          {row.name}
                        </span>
                      </div>
                    ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
