import React, { useState, useEffect } from 'react';
import { SignalsGrid } from './SignalsGrid';
import { CandlestickChart } from './CandlestickChart';

interface MainTabProps {
  onSignalClick?: (signal: any) => void;
  selectedSymbol: string;
  onSymbolSelect: (symbol: string) => void;
}

const instruments = [
  { symbol: 'XAU', name: 'Gold', color: '#eab308' },
  { symbol: 'XAG', name: 'Silver', color: '#94a3b8' },
  { symbol: 'US100', name: 'Nasdaq-100', color: '#3b82f6' },
  { symbol: 'BTC', name: 'Bitcoin', color: '#f97316' },
];

const timeframes = [
  { value: '1', label: '1m' },
  { value: '5', label: '5m' },
  { value: '15', label: '15m' },
  { value: '30', label: '30m' },
  { value: '60', label: '1H' },
  { value: 'D', label: '1D' },
];

export const MainTab: React.FC<MainTabProps> = ({
  onSignalClick,
  selectedSymbol,
  onSymbolSelect,
}) => {
  const [chartData, setChartData] = useState<any>(null);
  const [selectedTimeframe, setSelectedTimeframe] = useState(() => {
    return localStorage.getItem('cfd_timeframe') || '60';
  });
  const [loading, setLoading] = useState(false);

  useEffect(() => { localStorage.setItem('cfd_timeframe', selectedTimeframe); }, [selectedTimeframe]);

  const fetchChartData = async (symbol: string, resolution: string) => {
    try {
      setLoading(true);
      const response = await fetch(`/api/chart/${symbol}?resolution=${resolution}&count=150`);
      if (response.ok) {
        const data = await response.json();
        if (data.data && Array.isArray(data.data) && data.data.length > 0) {
          const validData = data.data.filter((candle: any) =>
            candle &&
            typeof candle.time === 'string' &&
            typeof candle.open === 'number' &&
            typeof candle.high === 'number' &&
            typeof candle.low === 'number' &&
            typeof candle.close === 'number' &&
            typeof candle.volume === 'number'
          );
          if (validData.length > 0) {
            setChartData({ ...data, data: validData });
          } else {
            setChartData({ error: 'Invalid data format' });
          }
        } else {
          setChartData({ error: data.error || 'No chart data available' });
        }
      }
    } catch (error) {
      setChartData({ error: 'Network error' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (selectedSymbol) {
      fetchChartData(selectedSymbol, selectedTimeframe);
    }
  }, [selectedSymbol, selectedTimeframe]);

  const handleSignalClick = (signal: any) => {
    if (signal.symbol && signal.symbol !== selectedSymbol) {
      onSymbolSelect(signal.symbol);
    }
    onSignalClick?.(signal);
  };

  const currentInstrument = instruments.find(i => i.symbol === selectedSymbol);

  return (
    <div className="flex flex-col h-full p-2 md:p-4 gap-2 md:gap-3 overflow-auto">
      {/* Chart Section */}
      <div className="flex-1 min-h-[300px] md:min-h-0 rounded-sm overflow-hidden" style={{ backgroundColor: '#0d1220', border: '1px solid #1a1f35' }}>
        {/* Chart Header */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between px-2 md:px-4 py-2 md:py-2.5 gap-2 sm:gap-0" style={{ borderBottom: '1px solid #1a1f35' }}>
          <div className="flex items-center gap-2 md:gap-3 w-full sm:w-auto">
            {/* Symbol Tabs - scrollable on mobile */}
            <div className="flex items-center gap-0.5 overflow-x-auto flex-shrink-0">
              {instruments.map((inst) => (
                <button
                  key={inst.symbol}
                  onClick={() => onSymbolSelect(inst.symbol)}
                  className="px-2 md:px-2.5 py-1 text-[11px] font-medium rounded-sm transition-all whitespace-nowrap flex-shrink-0"
                  style={{
                    color: selectedSymbol === inst.symbol ? '#e2e8f0' : '#4a5568',
                    backgroundColor: selectedSymbol === inst.symbol ? '#1a1f35' : 'transparent',
                    borderLeft: selectedSymbol === inst.symbol ? `2px solid ${inst.color}` : '2px solid transparent',
                  }}
                >
                  {inst.symbol}
                </button>
              ))}
            </div>
            <span className="text-[10px] hidden sm:inline" style={{ color: '#4a5568' }}>
              {currentInstrument?.name}
            </span>
            {chartData && !chartData.error && (() => {
              const isLive = chartData.source === 'alpha_vantage';
              const isCache = chartData.source === 'cache';
              const fetchedAt = chartData.fetched_at ? new Date(chartData.fetched_at + 'Z') : null;
              const ageMs = fetchedAt ? Date.now() - fetchedAt.getTime() : Infinity;
              const isStale = ageMs > 5 * 60 * 1000; // > 5 minutes
              const ageStr = fetchedAt
                ? ageMs < 60000 ? `${Math.floor(ageMs / 1000)}s ago`
                : ageMs < 3600000 ? `${Math.floor(ageMs / 60000)}m ago`
                : `${Math.floor(ageMs / 3600000)}h ago`
                : '';

              return (
                <div className="flex items-center gap-1">
                  <div
                    className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                    style={{ backgroundColor: isStale ? '#ef4444' : '#22c55e' }}
                    title={isStale ? 'Data is stale (>5 min old)' : 'Data is fresh'}
                  />
                  <span className="text-[9px] px-1 py-0.5 rounded-sm" style={{
                    backgroundColor: '#1a1f35',
                    color: isStale ? '#ef4444' : '#64748b',
                  }}>
                    {isLive ? 'LIVE' : isCache ? 'CACHED' : chartData.source?.toUpperCase()}
                    {ageStr ? ` ${ageStr}` : ''}
                  </span>
                </div>
              );
            })()}
          </div>

          {/* Timeframe Selector */}
          <div className="flex gap-0.5 overflow-x-auto w-full sm:w-auto">
            {timeframes.map((tf) => (
              <button
                key={tf.value}
                onClick={() => setSelectedTimeframe(tf.value)}
                className="px-2 py-1 text-[10px] font-medium rounded-sm transition-all flex-shrink-0"
                style={{
                  color: selectedTimeframe === tf.value ? '#e2e8f0' : '#4a5568',
                  backgroundColor: selectedTimeframe === tf.value ? '#1a1f35' : 'transparent',
                }}
              >
                {tf.label}
              </button>
            ))}
          </div>
        </div>

        {/* Chart Area */}
        <div className="p-1 md:p-2" style={{ height: 'calc(100% - 45px)' }}>
          {loading ? (
            <div className="h-full flex items-center justify-center" style={{ color: '#4a5568' }}>
              <div className="text-center">
                <div className="text-xs uppercase tracking-widest mb-1">Loading...</div>
                <div className="text-[10px]">{selectedSymbol} {timeframes.find(tf => tf.value === selectedTimeframe)?.label}</div>
              </div>
            </div>
          ) : chartData && chartData.data ? (
            <CandlestickChart
              key={`${selectedSymbol}-${selectedTimeframe}`}
              symbol={selectedSymbol}
              data={chartData.data}
              height={380}
              showVolume={true}
              showRSI={true}
            />
          ) : (
            <div className="h-full flex items-center justify-center" style={{ color: '#4a5568' }}>
              <div className="text-center">
                <div className="text-xs uppercase tracking-widest mb-1">No Data</div>
                <div className="text-[10px]">{chartData?.error || 'Select a symbol'}</div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Signals Section */}
      <div className="flex-shrink-0 min-h-[200px] md:min-h-0" style={{ height: 'auto', maxHeight: '320px' }}>
        <SignalsGrid onSignalClick={handleSignalClick} />
      </div>
    </div>
  );
};
