import React, { useState, useEffect } from 'react';

interface Signal {
  id?: string;
  symbol: string;
  score: number;
  direction: string;
  entry_point?: number;
  current_price?: number;
  take_profit?: number;
  stop_loss?: number;
  trend?: number[];
  confidence: number;
  risk_reward_ratio?: number;
  technical_score?: number;
  news_score?: number;
  components?: any[];
}

interface SignalsGridProps {
  signals?: Signal[];
  onSignalClick?: (signal: Signal) => void;
}

const defaultSignals: Signal[] = [
  { id: '1', symbol: 'XAU', score: 0.45, direction: 'buy', entry_point: 2050.00, take_profit: 2065.00, stop_loss: 2035.00, trend: [0.30, 0.35, 0.40, 0.42, 0.45], confidence: 0.72, risk_reward_ratio: 1.5 },
  { id: '2', symbol: 'XAG', score: 0.62, direction: 'buy', entry_point: 32.50, take_profit: 33.75, stop_loss: 31.25, trend: [0.40, 0.48, 0.55, 0.60, 0.62], confidence: 0.78, risk_reward_ratio: 2.0 },
  { id: '3', symbol: 'US100', score: -0.35, direction: 'sell', entry_point: 19500.00, take_profit: 19250.00, stop_loss: 19750.00, trend: [0.10, -0.05, -0.15, -0.25, -0.35], confidence: 0.68, risk_reward_ratio: 1.67 },
  { id: '4', symbol: 'BTC', score: 0.55, direction: 'buy', entry_point: 97250.00, take_profit: 98500.00, stop_loss: 96000.00, trend: [0.35, 0.42, 0.48, 0.52, 0.55], confidence: 0.71, risk_reward_ratio: 1.5 },
];

const MiniSparkline: React.FC<{ data: number[] }> = ({ data }) => {
  if (!data.length) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const points = data.map((val, idx) => {
    const x = (idx / (data.length - 1)) * 60;
    const y = 14 - ((val - min) / range) * 12;
    return `${x},${y}`;
  }).join(' ');
  const isUp = data[data.length - 1] > data[0];
  const color = isUp ? '#22c55e' : '#ef4444';

  return (
    <svg width="64" height="16" viewBox="0 0 64 16">
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.2" vectorEffect="non-scaling-stroke" />
    </svg>
  );
};

export const SignalsGrid: React.FC<SignalsGridProps> = ({ signals: externalSignals, onSignalClick }) => {
  const [signals, setSignals] = useState<Signal[]>(defaultSignals);
  const [loading, setLoading] = useState(false);
  const [tradingSymbol, setTradingSymbol] = useState<string | null>(null);

  useEffect(() => {
    if (externalSignals && externalSignals.length > 0) {
      setSignals(externalSignals);
      return;
    }

    const fetchSignals = async () => {
      try {
        setLoading(true);
        const response = await fetch('/api/signals');
        if (response.ok) {
          const data = await response.json();
          if (data.signals && data.signals.length > 0) {
            const transformedSignals = data.signals.map((sig: any, idx: number) => ({
              id: `${idx}`,
              symbol: sig.symbol,
              score: sig.score,
              direction: sig.direction.toLowerCase().includes('buy') ? 'buy' : sig.direction.toLowerCase().includes('sell') ? 'sell' : 'neutral',
              entry_point: sig.entry_point || sig.current_price,
              current_price: sig.current_price,
              take_profit: sig.take_profit,
              stop_loss: sig.stop_loss,
              confidence: sig.confidence,
              risk_reward_ratio: sig.risk_reward_ratio,
              technical_score: sig.technical_score,
              news_score: sig.news_score,
              components: sig.components,
              trend: [sig.score * 0.5, sig.score * 0.6, sig.score * 0.7, sig.score * 0.8, sig.score * 0.9, sig.score],
            }));
            setSignals(transformedSignals);
          }
        }
      } catch (error) {
        console.error('Failed to fetch signals:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchSignals();
    const interval = setInterval(fetchSignals, 15000);
    return () => clearInterval(interval);
  }, [externalSignals]);

  const openTrade = async (symbol: string, direction: string) => {
    setTradingSymbol(symbol);
    try {
      const response = await fetch(`/api/trade/open?symbol=${symbol}&direction=${direction}&size=0.01`, {
        method: 'POST',
      });
      if (response.ok) {
        const data = await response.json();
        console.log('Trade opened:', data);
      }
    } catch (error) {
      console.error('Failed to open trade:', error);
    } finally {
      setTradingSymbol(null);
    }
  };

  const getScoreColor = (score: number): string => {
    if (score > 0.5) return '#22c55e';
    if (score > 0.2) return '#4ade80';
    if (score > -0.2) return '#64748b';
    if (score > -0.5) return '#f87171';
    return '#ef4444';
  };

  const getScoreBarWidth = (score: number): number => {
    return Math.abs(score) * 100;
  };

  const formatPrice = (price: number | undefined): string => {
    if (price === undefined) return '--';
    if (price > 10000) return price.toFixed(0);
    if (price > 100) return price.toFixed(2);
    return price.toFixed(4);
  };

  return (
    <div className="h-full rounded-sm overflow-hidden flex flex-col" style={{ backgroundColor: '#0d1220', border: '1px solid #1a1f35' }}>
      {/* Header */}
      <div className="flex items-center justify-between px-3 md:px-4 py-2" style={{ borderBottom: '1px solid #1a1f35' }}>
        <span className="text-[11px] font-medium uppercase tracking-wider" style={{ color: '#64748b' }}>
          Trading Signals
        </span>
        <span className="text-[10px]" style={{ color: '#374151' }}>
          {signals.length} instruments
        </span>
      </div>

      {/* Mobile Card Layout */}
      <div className="flex-1 overflow-auto md:hidden">
        <div className="p-2 space-y-2">
          {signals.map((signal) => {
            const scoreColor = getScoreColor(signal.score);
            const isBuy = signal.direction === 'buy';
            const dirColor = isBuy ? '#22c55e' : signal.direction === 'sell' ? '#ef4444' : '#64748b';

            return (
              <div
                key={signal.id || signal.symbol}
                onClick={() => onSignalClick?.(signal)}
                className="rounded-sm p-3"
                style={{ backgroundColor: '#0b0f1a', border: '1px solid #131825' }}
              >
                {/* Row 1: Symbol, Direction, Score */}
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-xs" style={{ color: '#e2e8f0' }}>{signal.symbol}</span>
                    <span
                      className="text-[10px] font-bold px-2 py-0.5 rounded-sm"
                      style={{ color: dirColor, backgroundColor: `${dirColor}15` }}
                    >
                      {signal.direction.toUpperCase()}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <MiniSparkline data={signal.trend || []} />
                    <span className="font-bold text-xs" style={{ color: scoreColor }}>
                      {signal.score >= 0 ? '+' : ''}{signal.score.toFixed(2)}
                    </span>
                  </div>
                </div>

                {/* Row 2: Prices */}
                <div className="flex items-center justify-between text-[10px] mb-2">
                  <div>
                    <span style={{ color: '#4a5568' }}>Entry: </span>
                    <span style={{ color: '#94a3b8' }}>{formatPrice(signal.entry_point)}</span>
                  </div>
                  <div>
                    <span style={{ color: '#4a5568' }}>TP: </span>
                    <span style={{ color: '#22c55e' }}>{formatPrice(signal.take_profit)}</span>
                  </div>
                  <div>
                    <span style={{ color: '#4a5568' }}>SL: </span>
                    <span style={{ color: '#ef4444' }}>{formatPrice(signal.stop_loss)}</span>
                  </div>
                </div>

                {/* Row 3: Conf, R:R, Actions */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3 text-[10px]">
                    <span style={{ color: '#4a5568' }}>
                      Conf: <span style={{ color: '#94a3b8' }}>{(signal.confidence * 100).toFixed(0)}%</span>
                    </span>
                    <span style={{ color: '#4a5568' }}>
                      R:R <span style={{ color: '#94a3b8' }}>{signal.risk_reward_ratio ? signal.risk_reward_ratio.toFixed(1) : '--'}</span>
                    </span>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={(e) => { e.stopPropagation(); openTrade(signal.symbol, 'buy'); }}
                      disabled={tradingSymbol === signal.symbol}
                      className="px-3 py-1 text-[10px] font-bold rounded-sm transition-all"
                      style={{
                        backgroundColor: 'rgba(34, 197, 94, 0.1)',
                        color: '#22c55e',
                        border: '1px solid rgba(34, 197, 94, 0.2)',
                      }}
                    >
                      BUY
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); openTrade(signal.symbol, 'sell'); }}
                      disabled={tradingSymbol === signal.symbol}
                      className="px-3 py-1 text-[10px] font-bold rounded-sm transition-all"
                      style={{
                        backgroundColor: 'rgba(239, 68, 68, 0.1)',
                        color: '#ef4444',
                        border: '1px solid rgba(239, 68, 68, 0.2)',
                      }}
                    >
                      SELL
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Desktop Table Layout */}
      <div className="flex-1 overflow-auto hidden md:block">
        <table className="w-full text-[11px]">
          <thead>
            <tr style={{ borderBottom: '1px solid #1a1f35' }}>
              <th className="px-4 py-2 text-left font-medium uppercase tracking-wider" style={{ color: '#4a5568' }}>Symbol</th>
              <th className="px-3 py-2 text-center font-medium uppercase tracking-wider" style={{ color: '#4a5568' }}>Score</th>
              <th className="px-3 py-2 text-center font-medium uppercase tracking-wider" style={{ color: '#4a5568' }}>Trend</th>
              <th className="px-3 py-2 text-center font-medium uppercase tracking-wider" style={{ color: '#4a5568' }}>Signal</th>
              <th className="px-3 py-2 text-center font-medium uppercase tracking-wider" style={{ color: '#4a5568' }}>Conf.</th>
              <th className="px-3 py-2 text-right font-medium uppercase tracking-wider" style={{ color: '#4a5568' }}>Entry</th>
              <th className="px-3 py-2 text-right font-medium uppercase tracking-wider" style={{ color: '#4a5568' }}>TP</th>
              <th className="px-3 py-2 text-right font-medium uppercase tracking-wider" style={{ color: '#4a5568' }}>SL</th>
              <th className="px-3 py-2 text-center font-medium uppercase tracking-wider" style={{ color: '#4a5568' }}>R:R</th>
              <th className="px-3 py-2 text-center font-medium uppercase tracking-wider" style={{ color: '#4a5568' }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {signals.map((signal) => {
              const scoreColor = getScoreColor(signal.score);
              const isBuy = signal.direction === 'buy';
              const dirColor = isBuy ? '#22c55e' : signal.direction === 'sell' ? '#ef4444' : '#64748b';

              return (
                <tr
                  key={signal.id || signal.symbol}
                  onClick={() => onSignalClick?.(signal)}
                  className="cursor-pointer transition-colors"
                  style={{ borderBottom: '1px solid #131825' }}
                  onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'rgba(26, 31, 53, 0.5)')}
                  onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                >
                  <td className="px-4 py-2.5">
                    <span className="font-bold text-xs" style={{ color: '#e2e8f0' }}>{signal.symbol}</span>
                  </td>
                  <td className="px-3 py-2.5 text-center">
                    <div className="flex items-center justify-center gap-1.5">
                      <div className="w-12 h-1.5 rounded-full overflow-hidden" style={{ backgroundColor: '#1a1f35' }}>
                        <div
                          className="h-full rounded-full transition-all"
                          style={{
                            width: `${getScoreBarWidth(signal.score)}%`,
                            backgroundColor: scoreColor,
                            marginLeft: signal.score < 0 ? `${100 - getScoreBarWidth(signal.score)}%` : '0',
                          }}
                        />
                      </div>
                      <span className="font-bold" style={{ color: scoreColor }}>
                        {signal.score >= 0 ? '+' : ''}{signal.score.toFixed(2)}
                      </span>
                    </div>
                  </td>
                  <td className="px-3 py-2.5 text-center">
                    <MiniSparkline data={signal.trend || []} />
                  </td>
                  <td className="px-3 py-2.5 text-center">
                    <span
                      className="text-[10px] font-bold px-2 py-0.5 rounded-sm"
                      style={{
                        color: dirColor,
                        backgroundColor: `${dirColor}15`,
                      }}
                    >
                      {signal.direction.toUpperCase()}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 text-center" style={{ color: '#94a3b8' }}>
                    {(signal.confidence * 100).toFixed(0)}%
                  </td>
                  <td className="px-3 py-2.5 text-right" style={{ color: '#94a3b8' }}>
                    {formatPrice(signal.entry_point)}
                  </td>
                  <td className="px-3 py-2.5 text-right" style={{ color: '#22c55e' }}>
                    {formatPrice(signal.take_profit)}
                  </td>
                  <td className="px-3 py-2.5 text-right" style={{ color: '#ef4444' }}>
                    {formatPrice(signal.stop_loss)}
                  </td>
                  <td className="px-3 py-2.5 text-center" style={{ color: '#94a3b8' }}>
                    {signal.risk_reward_ratio ? signal.risk_reward_ratio.toFixed(1) : '--'}
                  </td>
                  <td className="px-3 py-2.5 text-center">
                    <div className="flex items-center justify-center gap-1">
                      <button
                        onClick={(e) => { e.stopPropagation(); openTrade(signal.symbol, 'buy'); }}
                        disabled={tradingSymbol === signal.symbol}
                        className="px-2 py-0.5 text-[9px] font-bold rounded-sm transition-all"
                        style={{
                          backgroundColor: 'rgba(34, 197, 94, 0.1)',
                          color: '#22c55e',
                          border: '1px solid rgba(34, 197, 94, 0.2)',
                        }}
                      >
                        BUY
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); openTrade(signal.symbol, 'sell'); }}
                        disabled={tradingSymbol === signal.symbol}
                        className="px-2 py-0.5 text-[9px] font-bold rounded-sm transition-all"
                        style={{
                          backgroundColor: 'rgba(239, 68, 68, 0.1)',
                          color: '#ef4444',
                          border: '1px solid rgba(239, 68, 68, 0.2)',
                        }}
                      >
                        SELL
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
