import React, { useState, useEffect } from 'react';

interface CandleData {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface CandlestickChartProps {
  symbol: string;
  data: CandleData[];
  height?: number;
  showVolume?: boolean;
  showRSI?: boolean;
}

export const CandlestickChart: React.FC<CandlestickChartProps> = ({
  symbol,
  data,
  height = 300,
  showVolume = true,
  showRSI = true,
}) => {
  const [rsiData, setRsiData] = useState<number[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [currentPrice, setCurrentPrice] = useState<number | null>(null);

  // Calculate RSI (14-period)
  useEffect(() => {
    if (data && data.length >= 14) {
      try {
        const closes = data.map(d => d.close);
        const rsi = calculateRSI(closes, 14);
        setRsiData(rsi);
        setError(null);
      } catch (error) {
        console.error('Error calculating RSI:', error);
        setRsiData([]);
        setError('RSI calculation failed');
      }
    } else {
      setRsiData([]);
      setError(null);
    }
  }, [data]);

  const calculateRSI = (prices: number[], period: number): number[] => {
    const rsi: number[] = [];
    const gains: number[] = [];
    const losses: number[] = [];

    // Calculate price changes
    for (let i = 1; i < prices.length; i++) {
      const change = prices[i] - prices[i - 1];
      gains.push(change > 0 ? change : 0);
      losses.push(change < 0 ? Math.abs(change) : 0);
    }

    // Calculate initial average gain and loss
    let avgGain = gains.slice(0, period).reduce((a, b) => a + b, 0) / period;
    let avgLoss = losses.slice(0, period).reduce((a, b) => a + b, 0) / period;

    // Calculate RSI for each period
    for (let i = period; i < gains.length; i++) {
      avgGain = (avgGain * (period - 1) + gains[i]) / period;
      avgLoss = (avgLoss * (period - 1) + losses[i]) / period;
      
      const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
      const rsiValue = avgLoss === 0 ? 100 : 100 - (100 / (1 + rs));
      rsi.push(rsiValue);
    }

    return rsi;
  };

  if (!data || data.length === 0) {
    return (
      <div className="border rounded-sm p-4 flex items-center justify-center"
           style={{ backgroundColor: '#0a0e27', borderColor: '#00ff41', height: `${height}px` }}>
        <div className="text-center" style={{ color: '#666' }}>
          <div className="font-mono text-xs uppercase tracking-widest mb-2">No Chart Data</div>
          <div className="text-xs">Select a symbol to view chart</div>
        </div>
      </div>
    );
  }

  // Validate data structure
  if (!data || !Array.isArray(data)) {
    return (
      <div className="border rounded-sm p-4 flex items-center justify-center"
           style={{ backgroundColor: '#0a0e27', borderColor: '#00ff41', height: `${height}px` }}>
        <div className="text-center" style={{ color: '#666' }}>
          <div className="font-mono text-xs uppercase tracking-widest mb-2">Invalid Data Format</div>
          <div className="text-xs">Expected array of candlestick data</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="border rounded-sm p-4 flex items-center justify-center"
           style={{ backgroundColor: '#0a0e27', borderColor: '#ff1f1f', height: `${height}px` }}>
        <div className="text-center" style={{ color: '#ff7f7f' }}>
          <div className="font-mono text-xs uppercase tracking-widest mb-2">Chart Error</div>
          <div className="text-xs">{error || 'Unknown error'}</div>
        </div>
      </div>
    );
  }

  // Validate data structure with error handling
  let validData: CandleData[] = [];
  try {
    validData = data.filter(d => {
      if (!d || typeof d !== 'object') return false;
      
      // Check for required fields with proper validation
      const hasValidOpen = typeof d.open === 'number' && !isNaN(d.open) && isFinite(d.open);
      const hasValidHigh = typeof d.high === 'number' && !isNaN(d.high) && isFinite(d.high);
      const hasValidLow = typeof d.low === 'number' && !isNaN(d.low) && isFinite(d.low);
      const hasValidClose = typeof d.close === 'number' && !isNaN(d.close) && isFinite(d.close);
      const hasValidVolume = typeof d.volume === 'number' && !isNaN(d.volume) && isFinite(d.volume);
      
      // Additional validation: high >= low, close within high-low range
      const priceLogicValid = d.high >= d.low && 
                             d.open >= d.low && d.open <= d.high &&
                             d.close >= d.low && d.close <= d.high;
      
      return hasValidOpen && hasValidHigh && hasValidLow && hasValidClose && hasValidVolume && priceLogicValid;
    });
  } catch (error) {
    console.error('Error validating chart data:', error);
    setError('Data validation failed');
    validData = [];
  }

  if (validData.length === 0) {
    return (
      <div className="border rounded-sm p-4 flex items-center justify-center"
           style={{ backgroundColor: '#0a0e27', borderColor: '#00ff41', height: `${height}px` }}>
        <div className="text-center" style={{ color: '#666' }}>
          <div className="font-mono text-xs uppercase tracking-widest mb-2">Invalid Data</div>
          <div className="text-xs">Chart data format is invalid</div>
        </div>
      </div>
    );
  }

  // Calculate chart metrics with error handling
  let prices, volumes, maxPrice, minPrice, maxVolume, minVolume, priceRange, volumeRange;
  try {
    prices = validData.map(d => d.close);
    volumes = validData.map(d => d.volume);
    maxPrice = Math.max(...validData.map(d => d.high));
    minPrice = Math.min(...validData.map(d => d.low));
    maxVolume = Math.max(...volumes);
    minVolume = Math.min(...volumes);
    priceRange = maxPrice - minPrice;
    volumeRange = maxVolume - minVolume;
    
    // Validate calculated ranges
    if (priceRange <= 0 || volumeRange < 0 || !isFinite(priceRange) || !isFinite(volumeRange)) {
      throw new Error('Invalid price or volume range');
    }
    
    // Calculate current price for the horizontal indicator
    const currentPrice = validData.length > 0 ? validData[validData.length - 1].close : null;
  } catch (error) {
    console.error('Error calculating chart metrics:', error);
    setError('Chart calculation failed');
    return (
      <div className="border rounded-sm p-4 flex items-center justify-center"
           style={{ backgroundColor: '#0a0e27', borderColor: '#ff1f1f', height: `${height}px` }}>
        <div className="text-center" style={{ color: '#ff7f7f' }}>
          <div className="font-mono text-xs uppercase tracking-widest mb-2">Calculation Error</div>
          <div className="text-xs">{typeof error === 'string' ? error : 'Failed to process chart data'}</div>
        </div>
      </div>
    );
  }

  // Chart dimensions - optimized for better fit
  const chartWidth = 1200; // Full width
  const chartHeight = showVolume ? 280 : 340; // Reduced height for better fit
  const volumeHeight = showVolume ? 50 : 0;
  const rsiHeight = showRSI ? 60 : 0;
  const totalHeight = chartHeight + volumeHeight + rsiHeight;

  // Interactive state for hover effects
  const [hoveredCandle, setHoveredCandle] = useState<number | null>(null);
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });

  // Generate candlesticks with better scaling
  const candlesticks = validData.map((candle, index) => {
    const x = (index / (validData.length - 1)) * chartWidth;
    const openY = chartHeight - ((candle.open - minPrice) / priceRange) * chartHeight;
    const closeY = chartHeight - ((candle.close - minPrice) / priceRange) * chartHeight;
    const highY = chartHeight - ((candle.high - minPrice) / priceRange) * chartHeight;
    const lowY = chartHeight - ((candle.low - minPrice) / priceRange) * chartHeight;
    
    const isBullish = candle.close > candle.open;
    const candleColor = isBullish ? '#00ff41' : '#ff1f1f';
    const wickColor = isBullish ? '#00ff41' : '#ff1f1f';
    
    // Better candle width calculation for more data points
    const candleSpacing = chartWidth / validData.length;
    const candleWidth = Math.max(3, candleSpacing * 0.8); // Slightly thinner for more candles
    const candleBodyHeight = Math.max(1, Math.abs(closeY - openY));
    const candleBodyY = Math.min(openY, closeY);

    return {
      index,
      x,
      openY,
      closeY,
      highY,
      lowY,
      candleColor,
      wickColor,
      candleWidth,
      candleBodyHeight,
      candleBodyY,
      isBullish,
      volume: candle.volume,
      rsi: rsiData[index - 14], // RSI starts after 14 periods
      data: candle, // Store original data for tooltip
    };
  });

  // Generate price levels for Y-axis (more granular)
  const priceLevels = [];
  const levelCount = 8; // More price levels
  for (let i = 0; i <= levelCount; i++) {
    const price = minPrice + (priceRange * i / levelCount);
    const y = chartHeight - (i / levelCount) * chartHeight;
    priceLevels.push({ price, y });
  }

  // Generate time labels for X-axis with better relative time handling
  const timeLabels = [];
  const maxLabels = 12; // Reduced for better readability
  const step = Math.max(1, Math.floor(validData.length / maxLabels));
  
  for (let i = 0; i < validData.length; i += step) {
    const timeStr = validData[i].time;
    // Handle different time formats (HH:MM, MM/DD, etc.)
    let displayTime = timeStr;
    if (timeStr.includes(':')) {
      // For HH:MM format, show as-is
      displayTime = timeStr;
    } else if (timeStr.includes('/')) {
      // For MM/DD format, show as-is
      displayTime = timeStr;
    } else {
      // For other formats, use first 5 chars
      displayTime = timeStr.slice(0, 5);
    }
    
    timeLabels.push({
      time: displayTime,
      x: (i / (validData.length - 1)) * chartWidth,
    });
  }

  // Handle mouse events for interactivity
  const handleMouseMove = (event: React.MouseEvent<SVGElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const chartX = (x / rect.width) * chartWidth;
    
    // Find closest candle
    const candleIndex = Math.round((chartX / chartWidth) * (candlesticks.length - 1));
    if (candleIndex >= 0 && candleIndex < candlesticks.length) {
      setHoveredCandle(candleIndex);
      setMousePosition({ x: event.clientX, y: event.clientY });
    }
  };

  const handleMouseLeave = () => {
    setHoveredCandle(null);
  };

  return (
    <div className="border rounded-sm p-3"
         style={{ backgroundColor: '#0a0e27', borderColor: '#00ff41' }}>
      
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="font-mono text-sm font-bold" style={{ color: '#00ff41' }}>
            {symbol}
          </div>
          <div className="text-xs" style={{ color: '#666' }}>
            Interactive Candlestick Chart
          </div>
          {data && data.length > 0 && (
            <div className="text-xs px-2 py-1 border rounded"
                 style={{ borderColor: '#1a1f2e', color: '#666' }}>
              {data[0].time} → {data[data.length-1].time}
            </div>
          )}
        </div>
        <div className="text-xs" style={{ color: '#666' }}>
          {validData.length} candles
        </div>
      </div>

      {/* Main Chart Area */}
      <div className="relative">
        <svg 
          width="100%" 
          height={height} 
          viewBox={`0 0 ${chartWidth + 60} ${totalHeight + 40}`} 
          preserveAspectRatio="xMidYMid meet"
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
          style={{ cursor: 'crosshair' }}
        >
          {/* Grid lines */}
          <g stroke="#1a1f2e" strokeWidth="1">
            {priceLevels.map((level, i) => (
              <line key={`grid-${i}`} x1="0" y1={level.y} x2={chartWidth} y2={level.y} strokeOpacity="0.7" />
            ))}
            {timeLabels.map((label, i) => (
              <line key={`vgrid-${i}`} x1={label.x} y1="0" x2={label.x} y2={chartHeight} strokeOpacity="0.7" />
            ))}
          </g>

          {/* Current Price Horizontal Line */}
          {currentPrice && (
            <g>
              <line
                x1="0"
                y1={chartHeight - ((currentPrice - minPrice) / priceRange) * chartHeight}
                x2={chartWidth}
                y2={chartHeight - ((currentPrice - minPrice) / priceRange) * chartHeight}
                stroke="#00ff41"
                strokeWidth="1"
                strokeDasharray="4,2"
                opacity="0.8"
              />
              <text
                x={chartWidth + 5}
                y={chartHeight - ((currentPrice - minPrice) / priceRange) * chartHeight + 4}
                fill="#00ff41"
                fontSize="12"
                fontFamily="monospace"
                fontWeight="bold"
              >
                {currentPrice.toFixed(2)}
              </text>
            </g>
          )}

          {/* Y-axis price labels */}
          <g fill="#666" fontSize="12" fontFamily="monospace">
            {priceLevels.map((level, i) => (
              <text key={`price-${i}`} x="-10" y={level.y + 4} textAnchor="end">
                {level.price.toFixed(0)}
              </text>
            ))}
          </g>

          {/* X-axis time labels */}
          <g fill="#666" fontSize="12" fontFamily="monospace">
            {timeLabels.map((label, i) => (
              <text key={`time-${i}`} x={label.x} y={chartHeight + 20} textAnchor="middle">
                {label.time}
              </text>
            ))}
          </g>

          {/* Candlesticks */}
          <g>
            {candlesticks.map((candle) => (
              <g key={`candle-${candle.index}`}>
                {/* High-Low wick */}
                <line
                  x1={candle.x}
                  y1={candle.highY}
                  x2={candle.x}
                  y2={candle.lowY}
                  stroke={candle.wickColor}
                  strokeWidth={hoveredCandle === candle.index ? "1" : "0.5"}
                  opacity={hoveredCandle === null || hoveredCandle === candle.index ? "1" : "0.6"}
                />
                {/* Candle body */}
                <rect
                  x={candle.x - candle.candleWidth / 2}
                  y={candle.candleBodyY}
                  width={candle.candleWidth}
                  height={Math.max(1, candle.candleBodyHeight)}
                  fill={candle.candleColor}
                  stroke={candle.candleColor}
                  strokeWidth={hoveredCandle === candle.index ? "0.8" : "0.3"}
                  opacity={hoveredCandle === null || hoveredCandle === candle.index ? "1" : "0.6"}
                />
                {/* Hover indicator */}
                {hoveredCandle === candle.index && (
                  <>
                    <line
                      x1={candle.x}
                      y1={0}
                      x2={candle.x}
                      y2={chartHeight}
                      stroke="#ffff00"
                      strokeWidth="0.5"
                      strokeDasharray="2,2"
                      opacity="0.7"
                    />
                    <circle
                      cx={candle.x}
                      cy={candle.closeY}
                      r="2"
                      fill="#ffff00"
                      stroke="#0a0e27"
                      strokeWidth="0.5"
                    />
                  </>
                )}
              </g>
            ))}
          </g>

          {/* Volume bars (if enabled) */}
          {showVolume && (
            <g>
              {candlesticks.map((candle) => {
                const barHeight = (candle.volume / maxVolume) * volumeHeight;
                const volumeY = chartHeight + volumeHeight - barHeight; // Fixed positioning
                return (
                  <rect
                    key={`volume-${candle.index}`}
                    x={candle.x - candle.candleWidth / 2}
                    y={volumeY}
                    width={candle.candleWidth}
                    height={barHeight}
                    fill={candle.candleColor}
                    fillOpacity={hoveredCandle === candle.index ? "0.8" : "0.4"}
                  />
                );
              })}
            </g>
          )}

          {/* RSI (if enabled) */}
          {showRSI && rsiData.length > 0 && (
            <g>
              {/* RSI background */}
              <rect
                x="0"
                y={chartHeight + volumeHeight}
                width={chartWidth}
                height={rsiHeight}
                fill="#1a1f2e"
                fillOpacity="0.3"
              />
              {/* RSI overbought/oversold zones */}
              <rect
                x="0"
                y={chartHeight + volumeHeight}
                width={chartWidth}
                height={rsiHeight * 0.3}
                fill="#ff1f1f"
                fillOpacity="0.1"
              />
              <rect
                x="0"
                y={chartHeight + volumeHeight + rsiHeight * 0.7}
                width={chartWidth}
                height={rsiHeight * 0.3}
                fill="#00ff41"
                fillOpacity="0.1"
              />
              {/* RSI levels */}
              <line x1="0" y1={chartHeight + volumeHeight + rsiHeight * 0.3} x2={chartWidth} y2={chartHeight + volumeHeight + rsiHeight * 0.3} stroke="#666" strokeWidth="1" strokeDasharray="2,2" />
              <line x1="0" y1={chartHeight + volumeHeight + rsiHeight * 0.5} x2={chartWidth} y2={chartHeight + volumeHeight + rsiHeight * 0.5} stroke="#666" strokeWidth="1" strokeDasharray="4,4" />
              <line x1="0" y1={chartHeight + volumeHeight + rsiHeight * 0.7} x2={chartWidth} y2={chartHeight + volumeHeight + rsiHeight * 0.7} stroke="#666" strokeWidth="1" strokeDasharray="2,2" />
              {/* RSI line */}
              <polyline
                points={rsiData.map((rsi, i) => {
                  const x = (i / (rsiData.length - 1)) * chartWidth;
                  const y = chartHeight + volumeHeight + rsiHeight - (rsi / 100) * rsiHeight;
                  return `${x},${y}`;
                }).join(' ')}
                fill="none"
                stroke="#ffff00"
                strokeWidth="2"
              />
              {/* RSI labels */}
              <text x="5" y={chartHeight + volumeHeight + 15} fill="#666" fontSize="14">RSI</text>
              <text x="5" y={chartHeight + volumeHeight + rsiHeight * 0.3 + 5} fill="#666" fontSize="12">70</text>
              <text x="5" y={chartHeight + volumeHeight + rsiHeight * 0.5 + 5} fill="#666" fontSize="12">50</text>
              <text x="5" y={chartHeight + volumeHeight + rsiHeight * 0.7 + 5} fill="#666" fontSize="12">30</text>
            </g>
          )}
        </svg>
      </div>

      {/* Interactive Tooltip */}
      {hoveredCandle !== null && candlesticks[hoveredCandle] && (
        <div 
          className="absolute border rounded p-2 text-xs font-mono z-10"
          style={{
            backgroundColor: '#0a0e27',
            borderColor: '#00ff41',
            color: '#00ff41',
            left: `${Math.min(80, (candlesticks[hoveredCandle].x / chartWidth) * 100)}%`,
            top: '10px',
            pointerEvents: 'none',
          }}
        >
          <div className="font-bold mb-1">{candlesticks[hoveredCandle].data.time}</div>
          <div>O: {candlesticks[hoveredCandle].data.open.toFixed(2)}</div>
          <div>H: {candlesticks[hoveredCandle].data.high.toFixed(2)}</div>
          <div>L: {candlesticks[hoveredCandle].data.low.toFixed(2)}</div>
          <div>C: {candlesticks[hoveredCandle].data.close.toFixed(2)}</div>
          <div>V: {(candlesticks[hoveredCandle].data.volume / 1000).toFixed(0)}K</div>
          {candlesticks[hoveredCandle].rsi && (
            <div>RSI: {candlesticks[hoveredCandle].rsi.toFixed(1)}</div>
          )}
        </div>
      )}

      {/* Legend and Stats */}
      <div className="mt-3 pt-3 border-t text-xs" style={{ borderColor: '#1a1f2e' }}>
        <div className="flex justify-between items-center">
          <div className="flex gap-4" style={{ color: '#666' }}>
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 bg-green-500"></div>
              <span>Bullish</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 bg-red-500"></div>
              <span>Bearish</span>
            </div>
          </div>
          <div className="text-right" style={{ color: '#666' }}>
            <div>High: {maxPrice.toFixed(2)}</div>
            <div>Low: {minPrice.toFixed(2)}</div>
            <div>Volume: {(volumes.reduce((a, b) => a + b, 0) / 1000).toFixed(0)}K</div>
          </div>
        </div>
      </div>
    </div>
  );
};