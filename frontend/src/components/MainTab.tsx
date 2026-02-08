import React, { useState, useEffect } from 'react';
import { SignalsGrid } from './SignalsGrid';
import { CandlestickChart } from './CandlestickChart';

interface MainTabProps {
  onSignalClick?: (signal: any) => void;
  selectedSymbol: string;
  onSymbolSelect: (symbol: string) => void;
}

const instruments = [
  { symbol: 'XAU', name: 'Gold' },
  { symbol: 'XAG', name: 'Silver' },
  { symbol: 'US100', name: 'Nasdaq-100' },
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
  const [selectedTimeframe, setSelectedTimeframe] = useState('60');
  const [loading, setLoading] = useState(false);

  const fetchChartData = async (symbol: string, resolution: string) => {
    try {
      setLoading(true);
      const response = await fetch(`/api/chart/${symbol}?resolution=${resolution}&count=150`);
      if (response.ok) {
        const data = await response.json();
        if (data.data && Array.isArray(data.data) && data.data.length > 0) {
          // Validate data structure
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
            setChartData({
              ...data,
              data: validData
            });
          } else {
            console.error('Invalid chart data structure:', data);
            setChartData({ error: 'Invalid data format' });
          }
        } else {
          setChartData({ error: data.error || 'No chart data available' });
        }
      } else {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        setChartData({ error: errorData.error || `HTTP ${response.status}` });
      }
    } catch (error) {
      console.error('Failed to fetch chart data:', error);
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
    // Update the selected symbol when a signal is clicked
    if (signal.symbol && signal.symbol !== selectedSymbol) {
      onSymbolSelect(signal.symbol);
    }
    onSignalClick?.(signal);
  };

  const currentInstrument = instruments.find(i => i.symbol === selectedSymbol);

  return (
    <div className="flex flex-col h-full">
      {/* Top Section - Chart */}
      <div className="border-b pb-4 mb-4" style={{ borderColor: '#1a1f2e', height: '480px' }}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <div
              className="font-mono text-sm font-bold"
              style={{ color: '#00ff41' }}
            >
              {selectedSymbol}
            </div>
            <div className="text-xs" style={{ color: '#666' }}>
              {currentInstrument?.name}
            </div>
            {chartData && (
              <div className="text-xs px-2 py-1 border rounded"
                   style={{ borderColor: '#1a1f2e', color: '#666' }}>
                {chartData.source === 'alpha_vantage' ? 'Live Data' : 'Simulated'}
              </div>
            )}
          </div>
          
          {/* Timeframe Selector */}
          <div className="flex gap-1">
            {timeframes.map((tf) => (
              <button
                key={tf.value}
                onClick={() => setSelectedTimeframe(tf.value)}
                className={`px-2 py-1 text-xs font-mono border transition ${
                  selectedTimeframe === tf.value ? 'bg-opacity-10' : ''
                }`}
                style={{
                  borderColor: selectedTimeframe === tf.value ? '#00ff41' : '#1a1f2e',
                  color: selectedTimeframe === tf.value ? '#00ff41' : '#666',
                  backgroundColor: selectedTimeframe === tf.value ? 'rgba(0, 255, 65, 0.1)' : 'transparent',
                }}
              >
                {tf.label}
              </button>
            ))}
          </div>
        </div>

        {/* Chart */}
        {loading ? (
          <div className="h-[430px] flex items-center justify-center" style={{ color: '#666' }}>
            <div className="text-center">
              <div className="font-mono text-xs uppercase tracking-widest mb-2">Loading Chart...</div>
              <div className="text-xs">{selectedSymbol} - {timeframes.find(tf => tf.value === selectedTimeframe)?.label}</div>
            </div>
          </div>
        ) : chartData && chartData.data ? (
          <CandlestickChart 
            key={`${selectedSymbol}-${selectedTimeframe}`} // Force re-render on timeframe change
            symbol={selectedSymbol} 
            data={chartData.data} 
            height={430} // Optimized height - fits well without scrolling
            showVolume={true}
            showRSI={true}
          />
        ) : (
          <div className="h-[430px] flex items-center justify-center" style={{ color: '#666' }}>
            <div className="text-center">
              <div className="font-mono text-xs uppercase tracking-widest mb-2">No Chart Data</div>
              <div className="text-xs">
                {chartData?.error ? `Error: ${chartData.error}` : 'Click a signal to load chart'}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Bottom Section - Signals Table */}
      <div className="flex-shrink-0" style={{ height: '320px' }}>
        <div className="flex items-center justify-between mb-3">
          <div
            className="font-mono text-xs uppercase tracking-widest font-bold"
            style={{ color: '#00ff41' }}
          >
            Trading Signals
          </div>
          <div className="text-xs" style={{ color: '#666' }}>
            Click any row to view chart →
          </div>
        </div>
        
        <SignalsGrid
          onSignalClick={handleSignalClick}
        />
      </div>
    </div>
  );
};