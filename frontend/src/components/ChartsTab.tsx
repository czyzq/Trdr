import React, { useState, useEffect } from 'react';
import { CandlestickChart } from './CandlestickChart';

interface ChartData {
  time: string;
  close: number;
  open: number;
  high: number;
  low: number;
  volume: number;
}

interface ChartResponse {
  symbol: string;
  data: ChartData[];
  resolution: string;
  count: number;
  source: string;
}

const instruments = [
  { symbol: 'XAU', name: 'Gold', color: '#eab308' },
  { symbol: 'XAG', name: 'Silver', color: '#94a3b8' },
  { symbol: 'US100', name: 'Nasdaq-100', color: '#3b82f6' },
  { symbol: 'BTC', name: 'Bitcoin', color: '#f97316' },
];

const resolutions = [
  { value: '15', label: '15m' },
  { value: '30', label: '30m' },
  { value: '60', label: '1H' },
  { value: 'D', label: '1D' },
];

export const ChartsTab: React.FC = () => {
  const [charts, setCharts] = useState<ChartResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedResolution, setSelectedResolution] = useState('60');

  const fetchChartData = async () => {
    try {
      setLoading(true);
      const chartData: ChartResponse[] = [];
      for (const instrument of instruments) {
        const response = await fetch(`/api/chart/${instrument.symbol}?resolution=${selectedResolution}&count=50`);
        if (response.ok) {
          const data = await response.json();
          if (data.data) chartData.push(data);
        }
      }
      setCharts(chartData);
    } catch (error) {
      console.error('Failed to fetch chart data:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchChartData();
    const interval = setInterval(fetchChartData, 30000);
    return () => clearInterval(interval);
  }, [selectedResolution]);

  if (loading && charts.length === 0) {
    return (
      <div className="h-full flex items-center justify-center" style={{ color: '#4a5568' }}>
        <div className="text-xs uppercase tracking-widest">Loading charts...</div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <span className="text-[11px] font-medium uppercase tracking-wider" style={{ color: '#64748b' }}>
          Multi-Chart View
        </span>
        <div className="flex gap-0.5">
          {resolutions.map((res) => (
            <button
              key={res.value}
              onClick={() => setSelectedResolution(res.value)}
              className="px-2 py-1 text-[10px] font-medium rounded-sm transition-all"
              style={{
                color: selectedResolution === res.value ? '#e2e8f0' : '#4a5568',
                backgroundColor: selectedResolution === res.value ? '#1a1f35' : 'transparent',
              }}
            >
              {res.label}
            </button>
          ))}
        </div>
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {instruments.map((instrument) => {
          const chartData = charts.find(c => c.symbol === instrument.symbol);
          return (
            <div
              key={instrument.symbol}
              className="rounded-sm overflow-hidden"
              style={{ backgroundColor: '#0d1220', border: '1px solid #1a1f35' }}
            >
              <div className="flex items-center justify-between px-3 py-2" style={{ borderBottom: '1px solid #1a1f35' }}>
                <div className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: instrument.color }} />
                  <span className="text-[11px] font-bold" style={{ color: '#e2e8f0' }}>{instrument.symbol}</span>
                  <span className="text-[10px]" style={{ color: '#4a5568' }}>{instrument.name}</span>
                </div>
                {chartData && (
                  <span className="text-[9px]" style={{ color: '#374151' }}>
                    {chartData.source === 'alpha_vantage' ? 'LIVE' : 'SIM'} | {chartData.count} pts
                  </span>
                )}
              </div>
              <div className="p-2">
                {chartData && chartData.data.length > 0 ? (
                  <CandlestickChart
                    symbol={instrument.symbol}
                    data={chartData.data}
                    height={220}
                    showVolume={true}
                    showRSI={true}
                  />
                ) : (
                  <div className="h-[220px] flex items-center justify-center" style={{ color: '#4a5568' }}>
                    <div className="text-[10px]">No data</div>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
