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

export const ChartsTab: React.FC = () => {
  const [charts, setCharts] = useState<ChartResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedResolution, setSelectedResolution] = useState('60');

  const instruments = [
    { symbol: 'XAU', name: 'Gold' },
    { symbol: 'XAG', name: 'Silver' },
    { symbol: 'US100', name: 'Nasdaq-100' },
  ];

  const resolutions = [
    { value: '15', label: '15min' },
    { value: '30', label: '30min' },
    { value: '60', label: '1H' },
    { value: 'D', label: 'Daily' },
  ];

  const fetchChartData = async () => {
    try {
      setLoading(true);
      const chartData: ChartResponse[] = [];

      for (const instrument of instruments) {
        const response = await fetch(`/api/chart/${instrument.symbol}?resolution=${selectedResolution}&count=50`);
        if (response.ok) {
          const data = await response.json();
          if (data.data) {
            chartData.push(data);
          }
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
    
    // Refresh every 30 seconds
    const interval = setInterval(fetchChartData, 30000);
    return () => clearInterval(interval);
  }, [selectedResolution]);

  if (loading && charts.length === 0) {
    return (
      <div
        className="border rounded-sm p-4 h-full flex items-center justify-center"
        style={{
          backgroundColor: '#0a0e27',
          borderColor: '#00ff41',
        }}
      >
        <div className="text-center">
          <div
            className="font-mono text-xs uppercase tracking-widest mb-2"
            style={{ color: '#00ff41' }}
          >
            Loading Charts...
          </div>
          <div style={{ color: '#666' }} className="text-xs">
            Fetching historical data
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className="border rounded-sm p-4 h-full overflow-auto"
      style={{
        backgroundColor: '#0a0e27',
        borderColor: '#00ff41',
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div
          className="font-mono text-xs uppercase tracking-widest font-bold"
          style={{ color: '#00ff41' }}
        >
          Price Charts
        </div>
        
        {/* Resolution Selector */}
        <div className="flex gap-1">
          {resolutions.map((res) => (
            <button
              key={res.value}
              onClick={() => setSelectedResolution(res.value)}
              className={`px-2 py-1 text-xs font-mono border transition ${
                selectedResolution === res.value ? 'bg-opacity-10' : ''
              }`}
              style={{
                borderColor: selectedResolution === res.value ? '#00ff41' : '#1a1f2e',
                color: selectedResolution === res.value ? '#00ff41' : '#666',
                backgroundColor: selectedResolution === res.value ? 'rgba(0, 255, 65, 0.1)' : 'transparent',
              }}
            >
              {res.label}
            </button>
          ))}
        </div>
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
        {instruments.map((instrument) => {
          const chartData = charts.find(c => c.symbol === instrument.symbol);
          
          return (
            <div key={instrument.symbol} className="border rounded-sm p-3"
                 style={{ borderColor: '#1a1f2e' }}>
              <div className="flex items-center justify-between mb-3">
                <div>
                  <div className="font-mono text-sm font-bold" style={{ color: '#00ff41' }}>
                    {instrument.symbol}
                  </div>
                  <div className="text-xs" style={{ color: '#666' }}>
                    {instrument.name}
                  </div>
                </div>
                {chartData && (
                  <div className="text-xs" style={{ color: '#666' }}>
                    {chartData.source === 'alpha_vantage' ? 'Live' : 'Simulated'}
                  </div>
                )}
              </div>
              
              {chartData && chartData.data.length > 0 ? (
                <CandlestickChart 
                  symbol={instrument.symbol} 
                  data={chartData.data} 
                  height={250}
                  showVolume={true}
                  showRSI={true}
                />
              ) : (
                <div className="text-center py-8" style={{ color: '#666' }}>
                  <div className="text-xs">No chart data available</div>
                </div>
              )}
              
              {chartData && chartData.data.length > 0 && (
                <div className="mt-2 pt-2 border-t text-xs"
                     style={{ borderColor: '#1a1f2e' }}>
                  <div className="flex justify-between" style={{ color: '#666' }}>
                    <span>Points: {chartData.count}</span>
                    <span>Last: {chartData.data[chartData.data.length - 1].close.toFixed(2)}</span>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Footer Info */}
      <div className="mt-4 pt-3 border-t text-xs"
           style={{ borderColor: '#1a1f2e' }}>
        <div className="flex justify-between" style={{ color: '#666' }}>
          <span>Data from Alpha Vantage API</span>
          <span>Updates every 30 seconds</span>
        </div>
      </div>
    </div>
  );
};