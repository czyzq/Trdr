import { useCallback, useEffect, useState } from "react";
import { apiUrl } from "../api";

// Shared multi-timeframe indicator board hook (GET /api/signals/board).

export interface BoardRow {
  name: string;
  timeframe: string;
  value: number | null;
  normalized: number | null;
  vote: "buy" | "sell" | "neutral";
  strength: number;
}

export interface BoardResponse {
  symbol: string;
  rows: BoardRow[];
  consensus: { buy: number; sell: number; neutral: number };
  generated_at: string;
}

export const useBoard = (symbol: string, pollMs = 30000) => {
  const [board, setBoard] = useState<BoardResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch(apiUrl(`signals/board?symbol=${symbol}`));
      const data = await response.json();
      if (response.ok) {
        setBoard(data);
        setError(null);
      } else {
        setBoard(null);
        setError(data.error || "Failed to load board");
      }
    } catch {
      setError("Failed to fetch indicator board");
    } finally {
      setLoading(false);
    }
  }, [symbol]);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, pollMs);
    return () => clearInterval(interval);
  }, [refresh, pollMs]);

  return { board, error, loading, refresh };
};
