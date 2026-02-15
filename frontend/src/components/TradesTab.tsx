import React, { useState, useEffect } from 'react';
import { apiUrl } from '../api';

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
  unrealized_pnl_pln: number;
  margin_pln: number;
  opened_at: string;
  status: string;
}

interface ClosedTrade {
  id: string;
  symbol: string;
  name: string;
  direction: string;
  size: number;
  entry_price: number;
  exit_price: number;
  pnl_usd: number;
  pnl_pln: number;
  opened_at: string;
  closed_at: string;
  result: string;
}

export const TradesTab: React.FC = () => {
  const [openPositions, setOpenPositions] = useState<Position[]>([]);
  const [closedTrades, setClosedTrades] = useState<ClosedTrade[]>([]);
  const [activeSection, setActiveSection] = useState<'open' | 'history'>(() => {
    const saved = localStorage.getItem('cfd_tradesSection');
    return (saved === 'history' ? 'history' : 'open');
  });
  const [stats, setStats] = useState({ win_count: 0, loss_count: 0, win_rate: 0, total_pnl_pln: 0, total_pnl_usd: 0 });
  const [closingId, setClosingId] = useState<string | null>(null);

  useEffect(() => { localStorage.setItem('cfd_tradesSection', activeSection); }, [activeSection]);

  const fetchData = async () => {
    try {
      const [openRes, histRes] = await Promise.all([
        fetch(apiUrl('trades/open')),
        fetch(apiUrl('trades/history'))
      ]);
      if (openRes.ok) {
        const data = await openRes.json();
        setOpenPositions(data.positions || []);
      }
      if (histRes.ok) {
        const data = await histRes.json();
        setClosedTrades(data.trades || []);
        setStats({
          win_count: data.win_count || 0,
          loss_count: data.loss_count || 0,
          win_rate: data.win_rate || 0,
          total_pnl_pln: data.total_pnl_pln || 0,
          total_pnl_usd: data.total_pnl_usd || 0,
        });
      }
    } catch (error) {
      console.error('Failed to fetch trades:', error);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 60000); // Refresh every 60 seconds
    return () => clearInterval(interval);
  }, []);

  const closeTrade = async (positionId: string) => {
    setClosingId(positionId);
    try {
      const response = await fetch(apiUrl(`trade/close/${positionId}`), { method: 'POST' });
      if (response.ok) {
        fetchData();
      }
    } catch (error) {
      console.error('Failed to close trade:', error);
    } finally {
      setClosingId(null);
    }
  };

  const formatPrice = (price: number): string => {
    if (price > 10000) return price.toFixed(0);
    if (price > 100) return price.toFixed(2);
    return price.toFixed(4);
  };

  const formatTime = (dateStr: string): string => {
    const date = new Date(dateStr);
    return date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  return (
    <div className="flex flex-col h-full p-2 md:p-4 gap-2 md:gap-3 overflow-auto">
      {/* Stats Bar */}
      <div className="flex flex-wrap items-center gap-2 md:gap-4 px-3 md:px-4 py-2 md:py-3 rounded-sm" style={{ backgroundColor: '#0d1220', border: '1px solid #1a1f35' }}>
        <StatPill label="Open" value={openPositions.length.toString()} color="#3b82f6" />
        <StatPill label="Closed" value={(stats.win_count + stats.loss_count).toString()} color="#64748b" />
        <StatPill label="Wins" value={stats.win_count.toString()} color="#22c55e" />
        <StatPill label="Losses" value={stats.loss_count.toString()} color="#ef4444" />
        <StatPill label="WR" value={`${stats.win_rate}%`} color={stats.win_rate >= 50 ? '#22c55e' : '#ef4444'} />
        <div className="flex items-center gap-2 ml-auto">
          <span className="text-[10px] uppercase tracking-wider hidden sm:inline" style={{ color: '#4a5568' }}>Total P&L:</span>
          <span className="text-xs md:text-sm font-bold" style={{ color: stats.total_pnl_pln >= 0 ? '#22c55e' : '#ef4444' }}>
            {stats.total_pnl_pln >= 0 ? '+' : ''}{stats.total_pnl_pln.toFixed(2)} PLN
          </span>
        </div>
      </div>

      {/* Section Toggle */}
      <div className="flex gap-1">
        <button
          onClick={() => setActiveSection('open')}
          className="px-3 py-1.5 text-[11px] font-medium uppercase tracking-wider rounded-sm transition-all"
          style={{
            color: activeSection === 'open' ? '#e2e8f0' : '#4a5568',
            backgroundColor: activeSection === 'open' ? '#1a1f35' : 'transparent',
          }}
        >
          Open ({openPositions.length})
        </button>
        <button
          onClick={() => setActiveSection('history')}
          className="px-3 py-1.5 text-[11px] font-medium uppercase tracking-wider rounded-sm transition-all"
          style={{
            color: activeSection === 'history' ? '#e2e8f0' : '#4a5568',
            backgroundColor: activeSection === 'history' ? '#1a1f35' : 'transparent',
          }}
        >
          History ({closedTrades.length})
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 rounded-sm overflow-hidden" style={{ backgroundColor: '#0d1220', border: '1px solid #1a1f35' }}>
        {activeSection === 'open' ? (
          <div className="h-full overflow-auto">
            {openPositions.length === 0 ? (
              <div className="h-full flex items-center justify-center" style={{ color: '#4a5568' }}>
                <div className="text-center">
                  <div className="text-xs uppercase tracking-widest mb-1">No Open Positions</div>
                  <div className="text-[10px]">Use the signals tab to open trades</div>
                </div>
              </div>
            ) : (
              <>
                {/* Mobile cards */}
                <div className="md:hidden p-2 space-y-2">
                  {openPositions.map((pos) => {
                    const pnlColor = pos.unrealized_pnl_pln >= 0 ? '#22c55e' : '#ef4444';
                    const dirColor = pos.direction === 'buy' ? '#22c55e' : '#ef4444';
                    return (
                      <div key={pos.id} className="rounded-sm p-3" style={{ backgroundColor: '#0b0f1a', border: '1px solid #131825' }}>
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-xs" style={{ color: '#e2e8f0' }}>{pos.symbol}</span>
                            <span className="text-[10px] font-bold px-2 py-0.5 rounded-sm" style={{ color: dirColor, backgroundColor: `${dirColor}15` }}>
                              {pos.direction.toUpperCase()}
                            </span>
                            <span className="text-[10px]" style={{ color: '#4a5568' }}>{pos.size}</span>
                          </div>
                          <span className="text-xs font-bold" style={{ color: pnlColor }}>
                            {pos.unrealized_pnl_pln >= 0 ? '+' : ''}{pos.unrealized_pnl_pln.toFixed(2)} PLN
                          </span>
                        </div>
                        <div className="flex items-center justify-between text-[10px] mb-2">
                          <div><span style={{ color: '#4a5568' }}>Entry: </span><span style={{ color: '#94a3b8' }}>{formatPrice(pos.entry_price)}</span></div>
                          <div><span style={{ color: '#4a5568' }}>Now: </span><span style={{ color: '#e2e8f0' }}>{formatPrice(pos.current_price)}</span></div>
                        </div>
                        <div className="flex items-center justify-between text-[10px] mb-2">
                          <div><span style={{ color: '#4a5568' }}>TP: </span><span style={{ color: '#22c55e' }}>{formatPrice(pos.take_profit)}</span></div>
                          <div><span style={{ color: '#4a5568' }}>SL: </span><span style={{ color: '#ef4444' }}>{formatPrice(pos.stop_loss)}</span></div>
                          <div><span style={{ color: '#4a5568' }}>{formatTime(pos.opened_at)}</span></div>
                        </div>
                        <button
                          onClick={() => closeTrade(pos.id)}
                          disabled={closingId === pos.id}
                          className="w-full py-1.5 text-[10px] font-bold rounded-sm transition-all"
                          style={{
                            backgroundColor: 'rgba(239, 68, 68, 0.1)',
                            color: '#ef4444',
                            border: '1px solid rgba(239, 68, 68, 0.3)',
                            opacity: closingId === pos.id ? 0.5 : 1,
                          }}
                        >
                          {closingId === pos.id ? 'CLOSING...' : 'CLOSE POSITION'}
                        </button>
                      </div>
                    );
                  })}
                </div>

                {/* Desktop table */}
                <table className="w-full text-[11px] hidden md:table">
                  <thead>
                    <tr style={{ borderBottom: '1px solid #1a1f35' }}>
                      <th className="px-4 py-2.5 text-left font-medium uppercase tracking-wider" style={{ color: '#4a5568' }}>Symbol</th>
                      <th className="px-3 py-2.5 text-center font-medium uppercase tracking-wider" style={{ color: '#4a5568' }}>Dir.</th>
                      <th className="px-3 py-2.5 text-center font-medium uppercase tracking-wider" style={{ color: '#4a5568' }}>Size</th>
                      <th className="px-3 py-2.5 text-right font-medium uppercase tracking-wider" style={{ color: '#4a5568' }}>Entry</th>
                      <th className="px-3 py-2.5 text-right font-medium uppercase tracking-wider" style={{ color: '#4a5568' }}>Current</th>
                      <th className="px-3 py-2.5 text-right font-medium uppercase tracking-wider" style={{ color: '#4a5568' }}>TP</th>
                      <th className="px-3 py-2.5 text-right font-medium uppercase tracking-wider" style={{ color: '#4a5568' }}>SL</th>
                      <th className="px-3 py-2.5 text-right font-medium uppercase tracking-wider" style={{ color: '#4a5568' }}>P&L (PLN)</th>
                      <th className="px-3 py-2.5 text-right font-medium uppercase tracking-wider" style={{ color: '#4a5568' }}>P&L (USD)</th>
                      <th className="px-3 py-2.5 text-center font-medium uppercase tracking-wider" style={{ color: '#4a5568' }}>Opened</th>
                      <th className="px-3 py-2.5 text-center font-medium uppercase tracking-wider" style={{ color: '#4a5568' }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {openPositions.map((pos) => {
                      const pnlColor = pos.unrealized_pnl_pln >= 0 ? '#22c55e' : '#ef4444';
                      const dirColor = pos.direction === 'buy' ? '#22c55e' : '#ef4444';
                      return (
                        <tr key={pos.id} style={{ borderBottom: '1px solid #131825' }}>
                          <td className="px-4 py-2.5">
                            <div>
                              <span className="font-bold text-xs" style={{ color: '#e2e8f0' }}>{pos.symbol}</span>
                              <span className="text-[9px] ml-1.5" style={{ color: '#4a5568' }}>{pos.name}</span>
                            </div>
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            <span className="text-[10px] font-bold px-2 py-0.5 rounded-sm" style={{ color: dirColor, backgroundColor: `${dirColor}15` }}>
                              {pos.direction.toUpperCase()}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-center" style={{ color: '#94a3b8' }}>{pos.size}</td>
                          <td className="px-3 py-2.5 text-right" style={{ color: '#94a3b8' }}>{formatPrice(pos.entry_price)}</td>
                          <td className="px-3 py-2.5 text-right" style={{ color: '#e2e8f0' }}>{formatPrice(pos.current_price)}</td>
                          <td className="px-3 py-2.5 text-right" style={{ color: '#22c55e' }}>{formatPrice(pos.take_profit)}</td>
                          <td className="px-3 py-2.5 text-right" style={{ color: '#ef4444' }}>{formatPrice(pos.stop_loss)}</td>
                          <td className="px-3 py-2.5 text-right font-bold" style={{ color: pnlColor }}>
                            {pos.unrealized_pnl_pln >= 0 ? '+' : ''}{pos.unrealized_pnl_pln.toFixed(2)}
                          </td>
                          <td className="px-3 py-2.5 text-right" style={{ color: pnlColor }}>
                            {pos.unrealized_pnl_usd >= 0 ? '+' : ''}{pos.unrealized_pnl_usd.toFixed(2)}
                          </td>
                          <td className="px-3 py-2.5 text-center" style={{ color: '#4a5568' }}>
                            {formatTime(pos.opened_at)}
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            <button
                              onClick={() => closeTrade(pos.id)}
                              disabled={closingId === pos.id}
                              className="px-3 py-1 text-[10px] font-bold rounded-sm transition-all"
                              style={{
                                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                                color: '#ef4444',
                                border: '1px solid rgba(239, 68, 68, 0.3)',
                                opacity: closingId === pos.id ? 0.5 : 1,
                              }}
                            >
                              {closingId === pos.id ? '...' : 'CLOSE'}
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </>
            )}
          </div>
        ) : (
          <div className="h-full overflow-auto">
            {closedTrades.length === 0 ? (
              <div className="h-full flex items-center justify-center" style={{ color: '#4a5568' }}>
                <div className="text-center">
                  <div className="text-xs uppercase tracking-widest mb-1">No Trade History</div>
                  <div className="text-[10px]">Closed trades will appear here</div>
                </div>
              </div>
            ) : (
              <>
                {/* Mobile cards */}
                <div className="md:hidden p-2 space-y-2">
                  {closedTrades.map((trade) => {
                    const pnlColor = trade.pnl_pln >= 0 ? '#22c55e' : '#ef4444';
                    const dirColor = trade.direction === 'buy' ? '#22c55e' : '#ef4444';
                    return (
                      <div key={trade.id} className="rounded-sm p-3" style={{ backgroundColor: '#0b0f1a', border: '1px solid #131825' }}>
                        <div className="flex items-center justify-between mb-1.5">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-xs" style={{ color: '#e2e8f0' }}>{trade.symbol}</span>
                            <span className="text-[10px] font-bold px-2 py-0.5 rounded-sm" style={{ color: dirColor, backgroundColor: `${dirColor}15` }}>
                              {trade.direction.toUpperCase()}
                            </span>
                            <span
                              className="text-[10px] font-bold px-2 py-0.5 rounded-sm"
                              style={{
                                color: trade.result === 'win' ? '#22c55e' : '#ef4444',
                                backgroundColor: trade.result === 'win' ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                              }}
                            >
                              {trade.result.toUpperCase()}
                            </span>
                          </div>
                          <span className="text-xs font-bold" style={{ color: pnlColor }}>
                            {trade.pnl_pln >= 0 ? '+' : ''}{trade.pnl_pln.toFixed(2)} PLN
                          </span>
                        </div>
                        <div className="flex items-center justify-between text-[10px]">
                          <div><span style={{ color: '#4a5568' }}>Entry: </span><span style={{ color: '#94a3b8' }}>{formatPrice(trade.entry_price)}</span></div>
                          <div><span style={{ color: '#4a5568' }}>Exit: </span><span style={{ color: '#94a3b8' }}>{formatPrice(trade.exit_price)}</span></div>
                          <div style={{ color: '#4a5568' }}>{formatTime(trade.closed_at)}</div>
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Desktop table */}
                <table className="w-full text-[11px] hidden md:table">
                  <thead>
                    <tr style={{ borderBottom: '1px solid #1a1f35' }}>
                      <th className="px-4 py-2.5 text-left font-medium uppercase tracking-wider" style={{ color: '#4a5568' }}>Symbol</th>
                      <th className="px-3 py-2.5 text-center font-medium uppercase tracking-wider" style={{ color: '#4a5568' }}>Dir.</th>
                      <th className="px-3 py-2.5 text-right font-medium uppercase tracking-wider" style={{ color: '#4a5568' }}>Entry</th>
                      <th className="px-3 py-2.5 text-right font-medium uppercase tracking-wider" style={{ color: '#4a5568' }}>Exit</th>
                      <th className="px-3 py-2.5 text-right font-medium uppercase tracking-wider" style={{ color: '#4a5568' }}>P&L (PLN)</th>
                      <th className="px-3 py-2.5 text-right font-medium uppercase tracking-wider" style={{ color: '#4a5568' }}>P&L (USD)</th>
                      <th className="px-3 py-2.5 text-center font-medium uppercase tracking-wider" style={{ color: '#4a5568' }}>Result</th>
                      <th className="px-3 py-2.5 text-center font-medium uppercase tracking-wider" style={{ color: '#4a5568' }}>Closed</th>
                    </tr>
                  </thead>
                  <tbody>
                    {closedTrades.map((trade) => {
                      const pnlColor = trade.pnl_pln >= 0 ? '#22c55e' : '#ef4444';
                      const dirColor = trade.direction === 'buy' ? '#22c55e' : '#ef4444';
                      return (
                        <tr key={trade.id} style={{ borderBottom: '1px solid #131825' }}>
                          <td className="px-4 py-2.5">
                            <span className="font-bold text-xs" style={{ color: '#e2e8f0' }}>{trade.symbol}</span>
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            <span className="text-[10px] font-bold px-2 py-0.5 rounded-sm" style={{ color: dirColor, backgroundColor: `${dirColor}15` }}>
                              {trade.direction.toUpperCase()}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-right" style={{ color: '#94a3b8' }}>{formatPrice(trade.entry_price)}</td>
                          <td className="px-3 py-2.5 text-right" style={{ color: '#94a3b8' }}>{formatPrice(trade.exit_price)}</td>
                          <td className="px-3 py-2.5 text-right font-bold" style={{ color: pnlColor }}>
                            {trade.pnl_pln >= 0 ? '+' : ''}{trade.pnl_pln.toFixed(2)}
                          </td>
                          <td className="px-3 py-2.5 text-right" style={{ color: pnlColor }}>
                            {trade.pnl_usd >= 0 ? '+' : ''}{trade.pnl_usd.toFixed(2)}
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            <span
                              className="text-[10px] font-bold px-2 py-0.5 rounded-sm"
                              style={{
                                color: trade.result === 'win' ? '#22c55e' : '#ef4444',
                                backgroundColor: trade.result === 'win' ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                              }}
                            >
                              {trade.result.toUpperCase()}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-center" style={{ color: '#4a5568' }}>
                            {formatTime(trade.closed_at)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

const StatPill: React.FC<{ label: string; value: string; color: string }> = ({ label, value, color }) => (
  <div className="flex items-center gap-1.5">
    <span className="text-[10px] uppercase tracking-wider" style={{ color: '#4a5568' }}>{label}:</span>
    <span className="text-[11px] font-bold" style={{ color }}>{value}</span>
  </div>
);
