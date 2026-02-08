import React, { useState, useEffect } from 'react';
import { ScoreGauge } from './ScoreGauge';
import { SimpleChart } from './SimpleChart';

interface Signal {
  id?: string;
  symbol: string;
  score: number; // -1 to +1
  direction: string;
  entry_point?: number;
  current_price?: number;
  take_profit?: number;
  stop_loss?: number;
  trend?: number[]; // sparkline data points
  confidence: number;
  risk_reward_ratio?: number;
}

interface SignalsGridProps {
  signals?: Signal[];
  onSignalClick?: (signal: Signal) => void;
}

const defaultSignals: Signal[] = [
  {
    id: '1',
    symbol: 'XAU',
    score: 0.45,
    direction: 'buy',
    entry_point: 2050.00,
    take_profit: 2065.00,
    stop_loss: 2035.00,
    trend: [0.30, 0.35, 0.40, 0.42, 0.45],
    confidence: 0.72,
    risk_reward_ratio: 1.5,
  },
  {
    id: '2',
    symbol: 'XAG',
    score: 0.62,
    direction: 'buy',
    entry_point: 32.50,
    take_profit: 33.75,
    stop_loss: 31.25,
    trend: [0.40, 0.48, 0.55, 0.60, 0.62],
    confidence: 0.78,
    risk_reward_ratio: 2.0,
  },
  {
    id: '3',
    symbol: 'US100',
    score: 0.55,
    direction: 'buy',
    entry_point: 19500.00,
    take_profit: 19750.00,
    stop_loss: 19250.00,
    trend: [0.35, 0.42, 0.48, 0.52, 0.55],
    confidence: 0.68,
    risk_reward_ratio: 1.67,
  },
];

const MiniSparkline: React.FC<{ data: number[] }> = ({ data }) => {
  if (!data.length) return null;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const points = data
    .map((val, idx) => {
      const x = (idx / (data.length - 1)) * 80;
      const y = 20 - ((val - min) / range) * 16;
      return `${x},${y}`;
    })
    .join(' ');

  // Determine color based on trend
  const isUp = data[data.length - 1] > data[0];
  const color = isUp ? '#00ff41' : '#ff1f1f';

  return (
    <svg width="84" height="20" viewBox="0 0 84 20" className="inline">
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
};

export const SignalsGrid: React.FC<SignalsGridProps> = ({
  signals: externalSignals,
  onSignalClick,
}) => {
  const [signals, setSignals] = useState<Signal[]>(defaultSignals);
  const [loading, setLoading] = useState(false);
  const [selectedSignal, setSelectedSignal] = useState<Signal | null>(null);
  const [showChart, setShowChart] = useState(false);

  // Update parent with signal count when signals change
  useEffect(() => {
    // This could be implemented to pass signal count up to parent
    // For now, we'll just use the length
  }, [signals]);

  useEffect(() => {
    if (externalSignals && externalSignals.length > 0) {
      setSignals(externalSignals);
      return;
    }

    // Fetch signals from backend
    const fetchSignals = async () => {
      try {
        setLoading(true);
        const response = await fetch('/api/signals');
        if (response.ok) {
          const data = await response.json();
          if (data.signals && data.signals.length > 0) {
            // Transform backend signals to frontend format
            // Show all signals from backend
            const transformedSignals = data.signals
              .map((sig: any, idx: number) => ({
                id: `${idx}`,
                symbol: sig.symbol,
                score: sig.score,
                direction: sig.direction.toLowerCase().includes('buy') ? 'buy' : 'sell',
                entry_point: sig.entry_point || sig.current_price,
                current_price: sig.current_price,
                take_profit: sig.take_profit,
                stop_loss: sig.stop_loss,
                confidence: sig.confidence,
                risk_reward_ratio: sig.risk_reward_ratio,
                trend: [sig.score * 0.5, sig.score * 0.6, sig.score * 0.7, sig.score * 0.8, sig.score * 0.9, sig.score],
              }));
            setSignals(transformedSignals);
          }
        }
      } catch (error) {
        console.error('Failed to fetch signals:', error);
        // Keep using default signals
      } finally {
        setLoading(false);
      }
    };

    fetchSignals();

    // Refresh signals every 10 seconds
    const interval = setInterval(fetchSignals, 10000);
    return () => clearInterval(interval);
  }, [externalSignals]);

  const handleSignalClick = (signal: Signal) => {
    setSelectedSignal(signal);
    setShowChart(true);
    onSignalClick?.(signal);
  };

  const closeChart = () => {
    setShowChart(false);
    setSelectedSignal(null);
  };

  return (
    <div
      className="flex-1 border rounded-sm overflow-hidden flex flex-col"
      style={{
        backgroundColor: '#0a0e27',
        borderColor: '#00ff41',
      }}
    >
      {/* Chart Modal */}
      {showChart && selectedSignal && (
        <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4">
          <div className="border rounded-sm w-full max-w-4xl max-h-[90vh] overflow-auto"
               style={{
                 backgroundColor: '#0a0e27',
                 borderColor: '#00ff41',
               }}>
            <div className="p-4 border-b flex items-center justify-between"
                 style={{ borderColor: '#00ff41' }}>
              <div className="font-mono text-sm uppercase tracking-widest font-bold"
                   style={{ color: '#00ff41' }}>
                {selectedSignal.symbol} - Technical Analysis
              </div>
              <button
                onClick={closeChart}
                className="px-3 py-1 border text-xs font-mono uppercase tracking-widest hover:bg-opacity-10 transition"
                style={{
                  borderColor: '#00ff41',
                  color: '#00ff41',
                }}
              >
                Close
              </button>
            </div>
            <div className="p-4">
              <SimpleChart symbol={selectedSignal.symbol} />
              <div className="mt-4 grid grid-cols-2 gap-4 text-xs">
                <div className="border p-3 rounded-sm"
                     style={{ borderColor: '#1a1f2e' }}>
                  <div className="font-bold mb-2" style={{ color: '#00ff41' }}>Signal Details</div>
                  <div className="space-y-1" style={{ color: '#aaa' }}>
                    <div>Score: <span className="font-bold">{selectedSignal.score.toFixed(3)}</span></div>
                    <div>Direction: <span className="font-bold" style={{color: selectedSignal.direction === 'buy' ? '#00ff41' : '#ff1f1f'}}>{selectedSignal.direction.toUpperCase()}</span></div>
                    <div>Confidence: <span className="font-bold">{(selectedSignal.confidence * 100).toFixed(1)}%</span></div>
                  </div>
                </div>
                <div className="border p-3 rounded-sm"
                     style={{ borderColor: '#1a1f2e' }}>
                  <div className="font-bold mb-2" style={{ color: '#00ff41' }}>Trade Levels</div>
                  <div className="space-y-1" style={{ color: '#aaa' }}>
                    <div>Entry: <span className="font-bold">{selectedSignal.entry_point?.toFixed(2) || 'N/A'}</span></div>
                    <div>Take Profit: <span className="font-bold" style={{color: '#00ff41'}}>{selectedSignal.take_profit?.toFixed(2) || 'N/A'}</span></div>
                    <div>Stop Loss: <span className="font-bold" style={{color: '#ff1f1f'}}>{selectedSignal.stop_loss?.toFixed(2) || 'N/A'}</span></div>
                    <div>Risk/Reward: <span className="font-bold">{selectedSignal.risk_reward_ratio?.toFixed(1) || 'N/A'}:1</span></div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
      {/* Header */}
      <div
        className="px-4 py-3 border-b"
        style={{ borderColor: '#00ff41' }}
      >
        <h3
          className="font-mono text-xs uppercase tracking-widest font-bold"
          style={{ color: '#00ff41' }}
        >
          Active Signals
        </h3>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-x-auto overflow-y-auto">
        <table className="w-full font-mono text-xs">
          <thead>
            <tr style={{ borderBottom: '1px solid #00ff41' }}>
              <th
                className="px-4 py-2 text-left uppercase font-bold tracking-widest"
                style={{ color: '#00ff41' }}
              >
                Symbol
              </th>
              <th
                className="px-4 py-2 text-center uppercase font-bold tracking-widest"
                style={{ color: '#00ff41' }}
              >
                Score
              </th>
              <th
                className="px-4 py-2 text-center uppercase font-bold tracking-widest"
                style={{ color: '#00ff41' }}
              >
                Trend
              </th>
              <th
                className="px-4 py-2 text-center uppercase font-bold tracking-widest"
                style={{ color: '#00ff41' }}
              >
                Signal
              </th>
              <th
                className="px-4 py-2 text-right uppercase font-bold tracking-widest"
                style={{ color: '#00ff41' }}
              >
                Entry
              </th>
              <th
                className="px-4 py-2 text-right uppercase font-bold tracking-widest"
                style={{ color: '#00ff41' }}
              >
                TP
              </th>
              <th
                className="px-4 py-2 text-right uppercase font-bold tracking-widest"
                style={{ color: '#00ff41' }}
              >
                SL
              </th>
              <th
                className="px-4 py-2 text-center uppercase font-bold tracking-widest"
                style={{ color: '#00ff41' }}
              >
                R:R
              </th>
            </tr>
          </thead>
          <tbody>
            {signals.map((signal) => {
              const scoreColor =
                signal.score > 0.7
                  ? '#00ff41'
                  : signal.score > 0.3
                  ? '#ffff00'
                  : signal.score > -0.3
                  ? '#ff7f7f'
                  : '#ff1f1f';

              const directionDisplay = signal.direction === 'buy' ? 'BUY' : 'SELL';
              const isLargePrice = (signal.entry_point || 0) > 1000;

              return (
                <tr
                  key={signal.id}
                  onClick={() => handleSignalClick(signal)}
                  className="border-b hover:bg-opacity-10 cursor-pointer transition"
                  style={{
                    borderColor: '#1a1f2e',
                    backgroundColor: 'rgba(0, 255, 65, 0.02)',
                  }}
                >
                  {/* Symbol */}
                  <td className="px-4 py-3">
                    <button
                      onClick={(e) => {
                        e.stopPropagation(); // Prevent row click
                        // You could add symbol-specific action here
                        console.log('Symbol clicked:', signal.symbol);
                      }}
                      className="font-bold hover:underline transition"
                      style={{ color: '#00ff41' }}
                      title={`View ${signal.symbol} chart`}
                    >
                      {signal.symbol}
                    </button>
                  </td>

                  {/* Score */}
                  <td className="px-4 py-3 text-center">
                    <span style={{ color: scoreColor }} className="font-bold">
                      {signal.score.toFixed(2)}
                    </span>
                  </td>

                  {/* Trend Sparkline */}
                  <td className="px-4 py-3 text-center">
                    <MiniSparkline data={signal.trend || []} />
                  </td>

                  {/* Direction */}
                  <td className="px-4 py-3 text-center">
                    <span
                      className="font-bold"
                      style={{
                        color: signal.direction === 'buy' ? '#00ff41' : '#ff1f1f',
                      }}
                    >
                      {directionDisplay}
                    </span>
                  </td>

                  {/* Entry Price */}
                  <td className="px-4 py-3 text-right" style={{ color: '#aaa' }}>
                    {typeof signal.entry_point === 'number'
                      ? isLargePrice
                        ? signal.entry_point.toFixed(0)
                        : signal.entry_point.toFixed(4)
                      : 'N/A'}
                  </td>

                  {/* Take Profit */}
                  <td className="px-4 py-3 text-right" style={{ color: '#00ff41' }}>
                    {typeof signal.take_profit === 'number'
                      ? isLargePrice
                        ? signal.take_profit.toFixed(0)
                        : signal.take_profit.toFixed(4)
                      : 'N/A'}
                  </td>

                  {/* Stop Loss */}
                  <td className="px-4 py-3 text-right" style={{ color: '#ff1f1f' }}>
                    {typeof signal.stop_loss === 'number'
                      ? isLargePrice
                        ? signal.stop_loss.toFixed(0)
                        : signal.stop_loss.toFixed(4)
                      : 'N/A'}
                  </td>

                  {/* Risk/Reward */}
                  <td className="px-4 py-3 text-center" style={{ color: '#aaa' }}>
                    {signal.risk_reward_ratio ? signal.risk_reward_ratio.toFixed(1) : 'N/A'}:1
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Footer stats */}
      <div
        className="px-4 py-2 border-t text-[10px]"
        style={{ borderColor: '#1a1f2e' }}
      >
        <div className="flex justify-between" style={{ color: '#666' }}>
          <span>Total Signals: {signals.length}</span>
          <span>
            Avg Score:{' '}
            {(
              signals.reduce((sum, s) => sum + s.score, 0) / signals.length
            ).toFixed(2)}
          </span>
        </div>
      </div>
    </div>
  );
};
