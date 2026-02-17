import React, { useState, useEffect } from 'react';
import { apiUrl } from '../api';

interface Position {
  id: string;
  symbol: string;
  direction: 'buy' | 'sell';
  entry_price: number;
  current_price: number;
  size: number;
  leverage: number;
  unrealized_pnl_usd: number;
  margin_usd: number;
  take_profit: number;
  stop_loss: number;
}

interface OpenPositionsSummaryProps {
  onClosePosition?: (id: string) => void;
}

export const OpenPositionsSummary: React.FC<OpenPositionsSummaryProps> = ({ onClosePosition }) => {
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(false);
  const [editingPosition, setEditingPosition] = useState<string | null>(null);
  const [editSl, setEditSl] = useState<number>(0);
  const [editTp, setEditTp] = useState<number>(0);

  const fetchPositions = async () => {
    try {
      const res = await fetch(apiUrl('trades/open'));
      if (res.ok) {
        const data = await res.json();
        setPositions(data.positions || []);
      }
    } catch (error) {
      console.error('Failed to fetch positions:', error);
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
      await fetch(apiUrl(`trade/close/${id}`), { method: 'POST' });
      await fetchPositions();
      onClosePosition?.(id);
    } catch (error) {
      console.error('Failed to close position:', error);
    } finally {
      setLoading(false);
    }
  };

  const startEdit = (pos: Position) => {
    setEditingPosition(pos.id);
    setEditSl(pos.stop_loss);
    setEditTp(pos.take_profit);
  };

  const saveEdit = async (id: string) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        stop_loss: editSl.toString(),
        take_profit: editTp.toString(),
      });
      await fetch(apiUrl(`trade/update/${id}?${params.toString()}`), { method: 'POST' });
      await fetchPositions();
      setEditingPosition(null);
    } catch (error) {
      console.error('Failed to update position:', error);
    } finally {
      setLoading(false);
    }
  };

  const cancelEdit = () => {
    setEditingPosition(null);
  };

  const getStep = (symbol: string) => {
    if (symbol === 'BTC') return 10;
    if (symbol === 'XAU') return 1;
    return 5;
  };

  if (positions.length === 0) {
    return (
      <div className="rounded-sm p-3" style={{ backgroundColor: '#0d1220', border: '1px solid #1a1f35' }}>
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-medium uppercase tracking-wider" style={{ color: '#4a5568' }}>
            Open Positions
          </span>
          <span className="text-[10px] px-2 py-0.5 rounded-sm" style={{ backgroundColor: '#1a1f35', color: '#64748b' }}>
            0
          </span>
        </div>
        <div className="text-[10px] mt-2" style={{ color: '#4a5568' }}>
          No open positions
        </div>
      </div>
    );
  }

  const totalPnl = positions.reduce((sum, p) => sum + (p.unrealized_pnl_usd || 0), 0);
  const totalMargin = positions.reduce((sum, p) => sum + (p.margin_usd || 0), 0);

  return (
    <div className="rounded-sm overflow-hidden" style={{ backgroundColor: '#0d1220', border: '1px solid #1a1f35' }}>
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2" style={{ borderBottom: '1px solid #1a1f35' }}>
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-medium uppercase tracking-wider" style={{ color: '#64748b' }}>
            Open Positions
          </span>
          <span className="text-[10px] px-2 py-0.5 rounded-sm" style={{ backgroundColor: '#1a1f35', color: '#e2e8f0' }}>
            {positions.length}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-[10px]">
            <span style={{ color: '#4a5568' }}>Margin: </span>
            <span style={{ color: '#e2e8f0' }}>${totalMargin.toFixed(2)}</span>
          </div>
          <div className="text-[10px]">
            <span style={{ color: '#4a5568' }}>P&L: </span>
            <span style={{ color: totalPnl >= 0 ? '#22c55e' : '#ef4444' }}>
              {totalPnl >= 0 ? '+' : ''}${totalPnl.toFixed(2)}
            </span>
          </div>
        </div>
      </div>

      {/* Positions List */}
      <div className="divide-y" style={{ borderColor: '#1a1f35' }}>
        {positions.map((pos) => {
          const pnlColor = (pos.unrealized_pnl_usd || 0) >= 0 ? '#22c55e' : '#ef4444';
          const dirColor = pos.direction === 'buy' ? '#22c55e' : '#ef4444';
          const pnlPct = pos.margin_usd > 0 ? ((pos.unrealized_pnl_usd || 0) / pos.margin_usd) * 100 : 0;
          const step = getStep(pos.symbol);
          const isEditing = editingPosition === pos.id;

          return (
            <div key={pos.id} className="px-3 py-2">
              {/* Main Row */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {/* Symbol & Direction */}
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-bold" style={{ color: '#e2e8f0' }}>{pos.symbol}</span>
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
                  <div className="text-[10px]" style={{ color: '#4a5568' }}>
                    {pos.size.toFixed(4)} lot (x{pos.leverage || 1}) @ {pos.entry_price.toFixed(2)}
                  </div>

                  {/* Current Price */}
                  <div className="text-[10px]" style={{ color: '#64748b' }}>
                    → {pos.current_price.toFixed(2)}
                  </div>
                </div>

                {/* P&L */}
                <div className="flex items-center gap-2">
                  <div className="text-right">
                    <div className="text-xs font-bold" style={{ color: pnlColor }}>
                      {pos.unrealized_pnl_usd >= 0 ? '+' : ''}${pos.unrealized_pnl_usd.toFixed(2)}
                    </div>
                    <div className="text-[9px]" style={{ color: pnlColor }}>
                      {pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(1)}%
                    </div>
                  </div>

                  {/* Edit Button */}
                  <button
                    onClick={() => startEdit(pos)}
                    disabled={loading}
                    className="px-2 py-1 text-[9px] font-bold rounded-sm transition-all"
                    style={{
                      backgroundColor: 'rgba(59, 130, 246, 0.1)',
                      color: '#3b82f6',
                      border: '1px solid rgba(59, 130, 246, 0.3)',
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
                      backgroundColor: 'rgba(239, 68, 68, 0.1)',
                      color: '#ef4444',
                      border: '1px solid rgba(239, 68, 68, 0.3)',
                      opacity: loading ? 0.5 : 1,
                    }}
                  >
                    CLOSE
                  </button>
                </div>
              </div>

              {/* SL/TP Display */}
              {!isEditing && (
                <div className="flex items-center gap-4 mt-1 text-[9px]">
                  <span style={{ color: '#4a5568' }}>
                    SL: <span style={{ color: '#ef4444' }}>{pos.stop_loss.toFixed(2)}</span>
                  </span>
                  <span style={{ color: '#4a5568' }}>
                    TP: <span style={{ color: '#22c55e' }}>{pos.take_profit.toFixed(2)}</span>
                  </span>
                </div>
              )}

              {/* Edit SL/TP Form */}
              {isEditing && (
                <div className="mt-2 p-2 rounded-sm" style={{ backgroundColor: '#0b0f1a' }}>
                  {/* Stop Loss */}
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px]" style={{ color: '#ef4444' }}>Stop Loss:</span>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => setEditSl(prev => prev - step)}
                        className="px-2 py-0.5 text-[10px] rounded"
                        style={{ backgroundColor: '#1a1f35', color: '#64748b' }}
                      >
                        −
                      </button>
                      <input
                        type="number"
                        value={editSl.toFixed(2)}
                        onChange={(e) => setEditSl(parseFloat(e.target.value) || 0)}
                        className="w-20 px-2 py-0.5 text-[10px] text-center rounded"
                        style={{ backgroundColor: '#1a1f35', border: '1px solid #ef444433', color: '#ef4444' }}
                      />
                      <button
                        onClick={() => setEditSl(prev => prev + step)}
                        className="px-2 py-0.5 text-[10px] rounded"
                        style={{ backgroundColor: '#1a1f35', color: '#64748b' }}
                      >
                        +
                      </button>
                    </div>
                  </div>

                  {/* Take Profit */}
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px]" style={{ color: '#22c55e' }}>Take Profit:</span>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => setEditTp(prev => prev - step)}
                        className="px-2 py-0.5 text-[10px] rounded"
                        style={{ backgroundColor: '#1a1f35', color: '#64748b' }}
                      >
                        −
                      </button>
                      <input
                        type="number"
                        value={editTp.toFixed(2)}
                        onChange={(e) => setEditTp(parseFloat(e.target.value) || 0)}
                        className="w-20 px-2 py-0.5 text-[10px] text-center rounded"
                        style={{ backgroundColor: '#1a1f35', border: '1px solid #22c55e33', color: '#22c55e' }}
                      />
                      <button
                        onClick={() => setEditTp(prev => prev + step)}
                        className="px-2 py-0.5 text-[10px] rounded"
                        style={{ backgroundColor: '#1a1f35', color: '#64748b' }}
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
                      style={{ backgroundColor: '#1a1f35', color: '#64748b' }}
                    >
                      Cancel
                    </button>
                    <button
                      onClick={() => saveEdit(pos.id)}
                      disabled={loading}
                      className="px-3 py-1 text-[9px] font-bold rounded-sm"
                      style={{
                        backgroundColor: 'rgba(34, 197, 94, 0.1)',
                        color: '#22c55e',
                        border: '1px solid rgba(34, 197, 94, 0.3)',
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
