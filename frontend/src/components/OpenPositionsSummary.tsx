import React, { useState, useEffect, useRef } from "react";
import { apiUrl } from "../api";

interface Position {
  id: string;
  symbol: string;
  direction: "buy" | "sell";
  entry_price: number;
  current_price: number;
  size: number;
  leverage: number;
  unrealized_pnl_usd: number;
  margin_usd: number;
  take_profit: number;
  stop_loss: number;
  opened_at: string;
}

interface SymbolConfig {
  step: number;
  min: number;
  max: number;
  decimals: number;
}

const SYMBOL_CONFIG: Record<string, SymbolConfig> = {
  BTC: { step: 1, min: 50000, max: 150000, decimals: 0 },
  XAU: { step: 0.1, min: 2500, max: 3500, decimals: 1 },
  XAG: { step: 0.01, min: 25, max: 40, decimals: 2 },
  US100: { step: 5, min: 15000, max: 25000, decimals: 0 },
  default: { step: 0.5, min: 0, max: 100000, decimals: 2 },
};

interface OpenPositionsSummaryProps {
  onClosePosition?: (id: string) => void;
  onSelectPosition?: (position: Position | null) => void;
  selectedPositionId?: string | null;
}

const formatDuration = (openedAt: string): string => {
  const opened = new Date(openedAt);
  const now = new Date();
  const diff = now.getTime() - opened.getTime();
  const hours = Math.floor(diff / 3600000);
  const minutes = Math.floor((diff % 3600000) / 60000);
  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  return `${minutes}m`;
};

const formatTime = (openedAt: string): string => {
  return new Date(openedAt).toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
  });
};

export const OpenPositionsSummary: React.FC<OpenPositionsSummaryProps> = ({
  onClosePosition,
  onSelectPosition,
  selectedPositionId,
}) => {
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(false);
  const [editingPosition, setEditingPosition] = useState<string | null>(null);
  const [editSl, setEditSl] = useState<number>(0);
  const [editTp, setEditTp] = useState<number>(0);
  const [editSlString, setEditSlString] = useState<string>("");
  const [editTpString, setEditTpString] = useState<string>("");
  const editSlTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const editTpTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [slDragStart, setSlDragStart] = useState<{
    x: number;
    value: number;
  } | null>(null);
  const [tpDragStart, setTpDragStart] = useState<{
    x: number;
    value: number;
  } | null>(null);

  const fetchPositions = async () => {
    try {
      const res = await fetch(apiUrl("trades/open"));
      if (res.ok) {
        const data = await res.json();
        setPositions(data.positions || []);
      }
    } catch (error) {
      console.error("Failed to fetch positions:", error);
    }
  };

  useEffect(() => {
    fetchPositions();
    const interval = setInterval(fetchPositions, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleClose = async (id: string) => {
    setLoading(true);
    try {
      await fetch(apiUrl(`trade/close/${id}`), { method: "POST" });
      await fetchPositions();
      onClosePosition?.(id);
    } catch (error) {
      console.error("Failed to close position:", error);
    } finally {
      setLoading(false);
    }
  };

  const startEdit = (pos: Position) => {
    setEditingPosition(pos.id);
    const cfg = getSymbolConfig(pos.symbol);
    setEditSl(pos.stop_loss);
    setEditTp(pos.take_profit);
    setEditSlString(pos.stop_loss.toFixed(cfg.decimals));
    setEditTpString(pos.take_profit.toFixed(cfg.decimals));
    // Clear any pending timeouts
    if (editSlTimeoutRef.current) {
      clearTimeout(editSlTimeoutRef.current);
      editSlTimeoutRef.current = null;
    }
    if (editTpTimeoutRef.current) {
      clearTimeout(editTpTimeoutRef.current);
      editTpTimeoutRef.current = null;
    }
  };

  const saveEdit = async (id: string) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        stop_loss: editSl.toString(),
        take_profit: editTp.toString(),
      });
      await fetch(apiUrl(`trade/update/${id}?${params.toString()}`), {
        method: "POST",
      });
      await fetchPositions();
      setEditingPosition(null);
    } catch (error) {
      console.error("Failed to update position:", error);
    } finally {
      setLoading(false);
    }
  };

  const cancelEdit = () => {
    setEditingPosition(null);
    // Clear pending timeouts
    if (editSlTimeoutRef.current) {
      clearTimeout(editSlTimeoutRef.current);
      editSlTimeoutRef.current = null;
    }
    if (editTpTimeoutRef.current) {
      clearTimeout(editTpTimeoutRef.current);
      editTpTimeoutRef.current = null;
    }
  };

  const getSymbolConfig = (symbol: string): SymbolConfig => {
    return SYMBOL_CONFIG[symbol] || SYMBOL_CONFIG.default;
  };

  // Slider drag handlers for SL
  const handleSlDragStart = (e: React.MouseEvent, value: number) => {
    setSlDragStart({ x: e.clientX, value });
  };

  const handleSlDragMove = (e: MouseEvent) => {
    if (!slDragStart) return;
    const config = getSymbolConfig(
      positions.find((p) => p.id === editingPosition)?.symbol || "",
    );
    const deltaPixels = e.clientX - slDragStart.x;
    const sensitivity = config.step * 2; // 2 units per 10 pixels
    const deltaValue =
      Math.round(((deltaPixels / 10) * sensitivity) / config.step) *
      config.step;
    const newValue = slDragStart.value + deltaValue;
    setEditSl(Math.max(config.min, Math.min(config.max, newValue)));
  };

  const handleSlDragEnd = () => {
    setSlDragStart(null);
  };

  // Slider drag handlers for TP
  const handleTpDragStart = (e: React.MouseEvent, value: number) => {
    setTpDragStart({ x: e.clientX, value });
  };

  const handleTpDragMove = (e: MouseEvent) => {
    if (!tpDragStart) return;
    const config = getSymbolConfig(
      positions.find((p) => p.id === editingPosition)?.symbol || "",
    );
    const deltaPixels = e.clientX - tpDragStart.x;
    const sensitivity = config.step * 2;
    const deltaValue =
      Math.round(((deltaPixels / 10) * sensitivity) / config.step) *
      config.step;
    const newValue = tpDragStart.value + deltaValue;
    setEditTp(Math.max(config.min, Math.min(config.max, newValue)));
  };

  const handleTpDragEnd = () => {
    setTpDragStart(null);
  };

  // Add/remove global event listeners for dragging
  useEffect(() => {
    if (slDragStart || tpDragStart) {
      const handleMove = (e: MouseEvent) => {
        if (slDragStart) handleSlDragMove(e);
        if (tpDragStart) handleTpDragMove(e);
      };
      const handleUp = () => {
        handleSlDragEnd();
        handleTpDragEnd();
      };
      window.addEventListener("mousemove", handleMove);
      window.addEventListener("mouseup", handleUp);
      return () => {
        window.removeEventListener("mousemove", handleMove);
        window.removeEventListener("mouseup", handleUp);
      };
    }
  }, [slDragStart, tpDragStart]);

  if (positions.length === 0) {
    return (
      <div
        className="rounded-sm p-3"
        style={{ backgroundColor: "#0d1220", border: "1px solid #1a1f35" }}
      >
        <div className="flex items-center justify-between">
          <span
            className="text-[11px] font-medium uppercase tracking-wider"
            style={{ color: "#4a5568" }}
          >
            Open Positions
          </span>
          <span
            className="text-[10px] px-2 py-0.5 rounded-sm"
            style={{ backgroundColor: "#1a1f35", color: "#64748b" }}
          >
            0
          </span>
        </div>
        <div className="text-[10px] mt-2" style={{ color: "#4a5568" }}>
          No open positions
        </div>
      </div>
    );
  }

  const totalPnl = positions.reduce(
    (sum, p) => sum + (p.unrealized_pnl_usd || 0),
    0,
  );
  const totalMargin = positions.reduce(
    (sum, p) => sum + (p.margin_usd || 0),
    0,
  );

  return (
    <div
      className="rounded-sm overflow-hidden"
      style={{ backgroundColor: "#0d1220", border: "1px solid #1a1f35" }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-3 py-2"
        style={{ borderBottom: "1px solid #1a1f35" }}
      >
        <div className="flex items-center gap-2">
          <span
            className="text-[11px] font-medium uppercase tracking-wider"
            style={{ color: "#64748b" }}
          >
            Open Positions
          </span>
          <span
            className="text-[10px] px-2 py-0.5 rounded-sm"
            style={{ backgroundColor: "#1a1f35", color: "#e2e8f0" }}
          >
            {positions.length}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-[10px]">
            <span style={{ color: "#4a5568" }}>Margin: </span>
            <span style={{ color: "#e2e8f0" }}>${totalMargin.toFixed(2)}</span>
          </div>
          <div className="text-[10px]">
            <span style={{ color: "#4a5568" }}>P&L: </span>
            <span style={{ color: totalPnl >= 0 ? "#22c55e" : "#ef4444" }}>
              {totalPnl >= 0 ? "+" : ""}${totalPnl.toFixed(2)}
            </span>
          </div>
        </div>
      </div>

      {/* Positions List */}
      <div className="divide-y" style={{ borderColor: "#1a1f35" }}>
        {positions.map((pos) => {
          const pnlColor =
            (pos.unrealized_pnl_usd || 0) >= 0 ? "#22c55e" : "#ef4444";
          const dirColor = pos.direction === "buy" ? "#22c55e" : "#ef4444";
          const pnlPct =
            pos.margin_usd > 0
              ? ((pos.unrealized_pnl_usd || 0) / pos.margin_usd) * 100
              : 0;
          const config = getSymbolConfig(pos.symbol);
          const isEditing = editingPosition === pos.id;

          return (
            <div key={pos.id} className="px-3 py-2">
              {/* Main Row */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {/* Symbol & Direction */}
                  <div className="flex items-center gap-1.5">
                    <span
                      className="text-xs font-bold"
                      style={{ color: "#e2e8f0" }}
                    >
                      {pos.symbol}
                    </span>
                    <span
                      className="text-[9px] font-bold px-1.5 py-0.5 rounded-sm"
                      style={{
                        color: dirColor,
                        backgroundColor: `${dirColor}15`,
                      }}
                    >
                      {pos.direction.toUpperCase()}
                    </span>
                  </div>

                  {/* Size, Leverage & Entry */}
                  <div className="text-[10px]" style={{ color: "#4a5568" }}>
                    {pos.size.toFixed(4)} lot (x{pos.leverage || 1}) @{" "}
                    {pos.entry_price.toFixed(2)}
                  </div>

                  {/* Current Price */}
                  <div className="text-[10px]" style={{ color: "#64748b" }}>
                    → {pos.current_price.toFixed(2)}
                  </div>
                </div>

                {/* P&L */}
                <div className="flex items-center gap-2">
                  <div className="text-right">
                    <div
                      className="text-xs font-bold"
                      style={{ color: pnlColor }}
                    >
                      {pos.unrealized_pnl_usd >= 0 ? "+" : ""}$
                      {pos.unrealized_pnl_usd.toFixed(2)}
                    </div>
                    <div className="text-[9px]" style={{ color: pnlColor }}>
                      {pnlPct >= 0 ? "+" : ""}
                      {pnlPct.toFixed(1)}%
                    </div>
                  </div>

                  {/* Edit Button */}
                  <button
                    onClick={() => startEdit(pos)}
                    disabled={loading}
                    className="px-2 py-1 text-[9px] font-bold rounded-sm transition-all"
                    style={{
                      backgroundColor: "rgba(59, 130, 246, 0.1)",
                      color: "#3b82f6",
                      border: "1px solid rgba(59, 130, 246, 0.3)",
                      opacity: loading ? 0.5 : 1,
                    }}
                  >
                    EDIT
                  </button>

                  {/* Close Button */}
                  <button
                    onClick={() => handleClose(pos.id)}
                    disabled={loading}
                    className="px-2 py-1 text-[9px] font-bold rounded-sm transition-all"
                    style={{
                      backgroundColor: "rgba(239, 68, 68, 0.1)",
                      color: "#ef4444",
                      border: "1px solid rgba(239, 68, 68, 0.3)",
                      opacity: loading ? 0.5 : 1,
                    }}
                  >
                    CLOSE
                  </button>
                </div>
              </div>

              {/* SL/TP Display + Open Time */}
              {!isEditing && (
                <div className="flex items-center justify-between mt-1">
                  <div className="flex items-center gap-4 text-[9px]">
                    <span style={{ color: "#4a5568" }}>
                      SL:{" "}
                      <span style={{ color: "#ef4444" }}>
                        {pos.stop_loss.toFixed(2)}
                      </span>
                    </span>
                    <span style={{ color: "#4a5568" }}>
                      TP:{" "}
                      <span style={{ color: "#22c55e" }}>
                        {pos.take_profit.toFixed(2)}
                      </span>
                    </span>
                  </div>
                  {pos.opened_at && (
                    <span className="text-[9px]" style={{ color: "#64748b" }}>
                      {formatTime(pos.opened_at)} (
                      {formatDuration(pos.opened_at)})
                    </span>
                  )}
                </div>
              )}

              {/* Edit SL/TP Form */}
              {isEditing && (
                <div
                  className="mt-2 p-2 rounded-sm"
                  style={{ backgroundColor: "#0b0f1a" }}
                >
                  {/* Stop Loss */}
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px]" style={{ color: "#ef4444" }}>
                      Stop Loss:
                    </span>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => setEditSl((prev) => prev - config.step)}
                        className="px-2 py-0.5 text-[10px] rounded"
                        style={{ backgroundColor: "#1a1f35", color: "#64748b" }}
                      >
                        −
                      </button>
                      <input
                        type="number"
                        value={editSl.toFixed(2)}
                        onChange={(e) =>
                          setEditSl(parseFloat(e.target.value) || 0)
                        }
                        className="w-20 px-2 py-0.5 text-[10px] text-center rounded"
                        style={{
                          backgroundColor: "#1a1f35",
                          border: "1px solid #ef444433",
                          color: "#ef4444",
                        }}
                      />
                      <button
                        onClick={() => setEditSl((prev) => prev + config.step)}
                        className="px-2 py-0.5 text-[10px] rounded"
                        style={{ backgroundColor: "#1a1f35", color: "#64748b" }}
                      >
                        +
                      </button>
                    </div>
                  </div>

                  {/* Take Profit */}
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px]" style={{ color: "#22c55e" }}>
                      Take Profit:
                    </span>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => setEditTp((prev) => prev - config.step)}
                        className="px-2 py-0.5 text-[10px] rounded"
                        style={{ backgroundColor: "#1a1f35", color: "#64748b" }}
                      >
                        −
                      </button>
                      <input
                        type="number"
                        value={editTp.toFixed(2)}
                        onChange={(e) =>
                          setEditTp(parseFloat(e.target.value) || 0)
                        }
                        className="w-20 px-2 py-0.5 text-[10px] text-center rounded"
                        style={{
                          backgroundColor: "#1a1f35",
                          border: "1px solid #22c55e33",
                          color: "#22c55e",
                        }}
                      />
                      <button
                        onClick={() => setEditTp((prev) => prev + config.step)}
                        className="px-2 py-0.5 text-[10px] rounded"
                        style={{ backgroundColor: "#1a1f35", color: "#64748b" }}
                      >
                        +
                      </button>
                    </div>
                  </div>

                  {/* Action Buttons */}
                  <div className="flex items-center justify-end gap-2">
                    <button
                      onClick={cancelEdit}
                      className="px-3 py-1 text-[9px] rounded-sm"
                      style={{ backgroundColor: "#1a1f35", color: "#64748b" }}
                    >
                      Cancel
                    </button>
                    <button
                      onClick={() => saveEdit(pos.id)}
                      disabled={loading}
                      className="px-3 py-1 text-[9px] font-bold rounded-sm"
                      style={{
                        backgroundColor: "rgba(34, 197, 94, 0.1)",
                        color: "#22c55e",
                        border: "1px solid rgba(34, 197, 94, 0.3)",
                        opacity: loading ? 0.5 : 1,
                      }}
                    >
                      Save
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
