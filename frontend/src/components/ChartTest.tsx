import React, { useState, useEffect } from 'react';

interface ChartTestProps {
  symbol?: string;
}

export const ChartTest: React.FC<ChartTestProps> = ({ symbol = 'XAU' }) => {
  const [chartData, setChartData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const testChartData = async () => {
    try {
      setLoading(true);
      setError(null);
      
      console.log(`Testing chart data for ${symbol}...`);
      
      const response = await fetch(`/api/chart/${symbol}?resolution=60&count=10`);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      console.log('Chart data received:', data);
      
      if (data.error) {
        throw new Error(data.error);
      }
      
      if (!data.data || !Array.isArray(data.data) || data.data.length === 0) {
        throw new Error('No chart data available');
      }
      
      // Validate data structure
      const firstCandle = data.data[0];
      const requiredFields = ['time', 'open', 'high', 'low', 'close', 'volume'];
      const missingFields = requiredFields.filter(field => !(field in firstCandle));
      
      if (missingFields.length > 0) {
        throw new Error(`Missing fields in chart data: ${missingFields.join(', ')}`);
      }
      
      // Validate data types and values
      const validationErrors: string[] = [];
      data.data.forEach((candle: any, index: number) => {
        if (typeof candle.open !== 'number' || isNaN(candle.open)) {
          validationErrors.push(`Candle ${index}: invalid open price`);
        }
        if (typeof candle.high !== 'number' || isNaN(candle.high)) {
          validationErrors.push(`Candle ${index}: invalid high price`);
        }
        if (typeof candle.low !== 'number' || isNaN(candle.low)) {
          validationErrors.push(`Candle ${index}: invalid low price`);
        }
        if (typeof candle.close !== 'number' || isNaN(candle.close)) {
          validationErrors.push(`Candle ${index}: invalid close price`);
        }
        if (typeof candle.volume !== 'number' || isNaN(candle.volume)) {
          validationErrors.push(`Candle ${index}: invalid volume`);
        }
        if (candle.high < candle.low) {
          validationErrors.push(`Candle ${index}: high < low`);
        }
        if (candle.open < candle.low || candle.open > candle.high) {
          validationErrors.push(`Candle ${index}: open outside high-low range`);
        }
        if (candle.close < candle.low || candle.close > candle.high) {
          validationErrors.push(`Candle ${index}: close outside high-low range`);
        }
      });
      
      if (validationErrors.length > 0) {
        throw new Error(`Data validation failed: ${validationErrors.join(', ')}`);
      }
      
      setChartData(data);
      console.log('Chart data validation successful!');
      
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      console.error('Chart test failed:', errorMessage);
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    testChartData();
  }, [symbol]);

  if (loading) {
    return (
      <div className="border rounded-sm p-4" style={{ backgroundColor: '#0a0e27', borderColor: '#00ff41' }}>
        <div className="font-mono text-xs uppercase tracking-widest mb-2" style={{ color: '#00ff41' }}>
          Testing Chart Data...
        </div>
        <div style={{ color: '#666' }}>Loading data for {symbol}</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="border rounded-sm p-4" style={{ backgroundColor: '#0a0e27', borderColor: '#ff1f1f' }}>
        <div className="font-mono text-xs uppercase tracking-widest mb-2" style={{ color: '#ff7f7f' }}>
          Chart Test Failed
        </div>
        <div style={{ color: '#666' }} className="text-xs">{error}</div>
        <button 
          onClick={testChartData}
          className="mt-2 px-2 py-1 text-xs border"
          style={{ borderColor: '#1a1f2e', color: '#666' }}
        >
          Retry
        </button>
      </div>
    );
  }

  if (!chartData) {
    return (
      <div className="border rounded-sm p-4" style={{ backgroundColor: '#0a0e27', borderColor: '#00ff41' }}>
        <div className="font-mono text-xs uppercase tracking-widest mb-2" style={{ color: '#00ff41' }}>
          No Chart Data
        </div>
        <div style={{ color: '#666' }}>No data available for {symbol}</div>
      </div>
    );
  }

  const lastCandle = chartData.data[chartData.data.length - 1];
  
  return (
    <div className="border rounded-sm p-4" style={{ backgroundColor: '#0a0e27', borderColor: '#00ff41' }}>
      <div className="flex items-center justify-between mb-3">
        <div className="font-mono text-xs uppercase tracking-widest" style={{ color: '#00ff41' }}>
          Chart Test Success
        </div>
        <div className="text-xs" style={{ color: '#666' }}>
          {chartData.source}
        </div>
      </div>
      
      <div className="grid grid-cols-2 gap-4 text-xs" style={{ color: '#666' }}>
        <div>
          <div className="font-mono mb-1">Symbol: {chartData.symbol}</div>
          <div>Resolution: {chartData.resolution}</div>
          <div>Count: {chartData.count}</div>
        </div>
        <div>
          <div className="font-mono mb-1">Last Candle:</div>
          <div>Open: {lastCandle.open.toFixed(2)}</div>
          <div>High: {lastCandle.high.toFixed(2)}</div>
          <div>Low: {lastCandle.low.toFixed(2)}</div>
          <div>Close: {lastCandle.close.toFixed(2)}</div>
          <div>Volume: {lastCandle.volume.toLocaleString()}</div>
        </div>
      </div>
      
      <div className="mt-3 pt-3 border-t" style={{ borderColor: '#1a1f2e' }}>
        <div className="text-xs" style={{ color: '#666' }}>
          ✓ Data structure valid
          <br />✓ All required fields present
          <br />✓ Price logic validated
          <br />✓ Ready for candlestick chart
        </div>
      </div>
    </div>
  );
};