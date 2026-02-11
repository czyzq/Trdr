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
  const [hoveredCandle, setHoveredCandle] = useState<number | null>(null);

  useEffect(() => {
    if (data && data.length >= 14) {
      const closes = data.map(d => d.close);
      setRsiData(calculateRSI(closes, 14));
    } else {
      setRsiData([]);
    }
  }, [data]);

  const calculateRSI = (prices: number[], period: number): number[] => {
    const rsi: number[] = [];
    const gains: number[] = [];
    const losses: number[] = [];
    for (let i = 1; i < prices.length; i++) {
      const change = prices[i] - prices[i - 1];
      gains.push(change > 0 ? change : 0);
      losses.push(change < 0 ? Math.abs(change) : 0);
    }
    let avgGain = gains.slice(0, period).reduce((a, b) => a + b, 0) / period;
    let avgLoss = losses.slice(0, period).reduce((a, b) => a + b, 0) / period;
    for (let i = period; i < gains.length; i++) {
      avgGain = (avgGain * (period - 1) + gains[i]) / period;
      avgLoss = (avgLoss * (period - 1) + losses[i]) / period;
      const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
      rsi.push(avgLoss === 0 ? 100 : 100 - (100 / (1 + rs)));
    }
    return rsi;
  };

  if (!data || data.length === 0) {
    return (
      <div className="h-full flex items-center justify-center" style={{ color: '#4a5568' }}>
        <div className="text-xs uppercase tracking-widest">No chart data</div>
      </div>
    );
  }

  // Validate data
  const validData = data.filter(d =>
    d && typeof d.open === 'number' && typeof d.high === 'number' &&
    typeof d.low === 'number' && typeof d.close === 'number' &&
    typeof d.volume === 'number' && isFinite(d.open) && isFinite(d.close) &&
    d.high >= d.low
  );

  if (validData.length === 0) return null;

  const prices = validData.map(d => d.close);
  const volumes = validData.map(d => d.volume);
  const maxPrice = Math.max(...validData.map(d => d.high));
  const minPrice = Math.min(...validData.map(d => d.low));
  const maxVolume = Math.max(...volumes);
  const priceRange = maxPrice - minPrice || 1;

  // Layout
  const chartWidth = 1100;
  const priceChartH = showVolume ? (showRSI ? 220 : 280) : (showRSI ? 260 : 340);
  const volumeH = showVolume ? 40 : 0;
  const rsiH = showRSI ? 50 : 0;
  const gapH = 8;
  const totalH = priceChartH + (showVolume ? volumeH + gapH : 0) + (showRSI ? rsiH + gapH : 0) + 25;
  const leftPad = 0;
  const rightPad = 55;
  const usableWidth = chartWidth - rightPad;

  const currentPrice = validData[validData.length - 1].close;
  const prevClose = validData.length > 1 ? validData[validData.length - 2].close : currentPrice;
  const priceChange = currentPrice - prevClose;
  const priceChangeStr = `${priceChange >= 0 ? '+' : ''}${priceChange.toFixed(2)}`;

  // Price levels
  const priceLevels = [];
  const levelCount = 6;
  for (let i = 0; i <= levelCount; i++) {
    const price = minPrice + (priceRange * i / levelCount);
    const y = priceChartH - (i / levelCount) * priceChartH;
    priceLevels.push({ price, y });
  }

  // Time labels
  const timeLabels: { time: string; x: number }[] = [];
  const maxLabels = 10;
  const step = Math.max(1, Math.floor(validData.length / maxLabels));
  for (let i = 0; i < validData.length; i += step) {
    timeLabels.push({
      time: validData[i].time,
      x: (i / (validData.length - 1)) * usableWidth,
    });
  }

  // Candlesticks
  const candleSpacing = usableWidth / validData.length;
  const candleWidth = Math.max(2, candleSpacing * 0.7);

  const candlesticks = validData.map((candle, index) => {
    const x = (index / (validData.length - 1)) * usableWidth;
    const openY = priceChartH - ((candle.open - minPrice) / priceRange) * priceChartH;
    const closeY = priceChartH - ((candle.close - minPrice) / priceRange) * priceChartH;
    const highY = priceChartH - ((candle.high - minPrice) / priceRange) * priceChartH;
    const lowY = priceChartH - ((candle.low - minPrice) / priceRange) * priceChartH;
    const isBullish = candle.close >= candle.open;

    return {
      index, x, openY, closeY, highY, lowY, isBullish,
      bodyY: Math.min(openY, closeY),
      bodyH: Math.max(1, Math.abs(closeY - openY)),
      color: isBullish ? '#22c55e' : '#ef4444',
      volume: candle.volume,
      data: candle,
      rsi: rsiData[index - 14],
    };
  });

  const handleMouseMove = (event: React.MouseEvent<SVGElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const chartX = (x / rect.width) * chartWidth;
    const idx = Math.round((chartX / usableWidth) * (candlesticks.length - 1));
    if (idx >= 0 && idx < candlesticks.length) setHoveredCandle(idx);
  };

  return (
    <div className="h-full relative">
      {/* Price Info */}
      <div className="flex items-center gap-3 mb-1 px-1">
        <span className="text-sm font-bold" style={{ color: '#e2e8f0' }}>{symbol}</span>
        <span className="text-sm font-bold" style={{ color: priceChange >= 0 ? '#22c55e' : '#ef4444' }}>
          {currentPrice.toFixed(2)}
        </span>
        <span className="text-[10px]" style={{ color: priceChange >= 0 ? '#22c55e' : '#ef4444' }}>
          {priceChangeStr}
        </span>
        {hoveredCandle !== null && candlesticks[hoveredCandle] && (
          <div className="flex items-center gap-2 ml-auto text-[10px]" style={{ color: '#64748b' }}>
            <span>O: {candlesticks[hoveredCandle].data.open.toFixed(2)}</span>
            <span>H: {candlesticks[hoveredCandle].data.high.toFixed(2)}</span>
            <span>L: {candlesticks[hoveredCandle].data.low.toFixed(2)}</span>
            <span>C: {candlesticks[hoveredCandle].data.close.toFixed(2)}</span>
            <span>V: {(candlesticks[hoveredCandle].data.volume / 1000).toFixed(0)}K</span>
            {candlesticks[hoveredCandle].rsi !== undefined && (
              <span>RSI: {candlesticks[hoveredCandle].rsi.toFixed(1)}</span>
            )}
          </div>
        )}
      </div>

      <svg
        width="100%"
        height={height}
        viewBox={`0 0 ${chartWidth} ${totalH}`}
        preserveAspectRatio="xMidYMid meet"
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHoveredCandle(null)}
        style={{ cursor: 'crosshair' }}
      >
        {/* Grid */}
        <g stroke="#131825" strokeWidth="1">
          {priceLevels.map((l, i) => (
            <line key={`g-${i}`} x1={leftPad} y1={l.y} x2={usableWidth} y2={l.y} />
          ))}
        </g>

        {/* Price labels */}
        <g fill="#374151" fontSize="10" fontFamily="monospace">
          {priceLevels.map((l, i) => (
            <text key={`p-${i}`} x={usableWidth + 5} y={l.y + 3} textAnchor="start">
              {l.price.toFixed(0)}
            </text>
          ))}
        </g>

        {/* Current Price Line */}
        <line
          x1={leftPad} y1={priceChartH - ((currentPrice - minPrice) / priceRange) * priceChartH}
          x2={usableWidth} y2={priceChartH - ((currentPrice - minPrice) / priceRange) * priceChartH}
          stroke={priceChange >= 0 ? '#22c55e' : '#ef4444'}
          strokeWidth="0.5" strokeDasharray="3,3" opacity="0.6"
        />
        <text
          x={usableWidth + 5}
          y={priceChartH - ((currentPrice - minPrice) / priceRange) * priceChartH + 3}
          fill={priceChange >= 0 ? '#22c55e' : '#ef4444'}
          fontSize="10" fontFamily="monospace" fontWeight="bold"
        >
          {currentPrice.toFixed(2)}
        </text>

        {/* Candlesticks */}
        <g>
          {candlesticks.map((c) => (
            <g key={`c-${c.index}`}>
              <line x1={c.x} y1={c.highY} x2={c.x} y2={c.lowY}
                stroke={c.color} strokeWidth={hoveredCandle === c.index ? '1' : '0.5'}
                opacity={hoveredCandle === null || hoveredCandle === c.index ? '1' : '0.5'}
              />
              <rect
                x={c.x - candleWidth / 2} y={c.bodyY} width={candleWidth} height={Math.max(1, c.bodyH)}
                fill={c.color} stroke={c.color} strokeWidth="0.3"
                opacity={hoveredCandle === null || hoveredCandle === c.index ? '1' : '0.5'}
              />
            </g>
          ))}
        </g>

        {/* Hover crosshair */}
        {hoveredCandle !== null && candlesticks[hoveredCandle] && (
          <line
            x1={candlesticks[hoveredCandle].x} y1={0}
            x2={candlesticks[hoveredCandle].x} y2={priceChartH}
            stroke="#374151" strokeWidth="0.5" strokeDasharray="2,2"
          />
        )}

        {/* Volume */}
        {showVolume && (
          <g>
            <text x={5} y={priceChartH + gapH + 10} fill="#374151" fontSize="9" fontFamily="monospace">VOL</text>
            {candlesticks.map((c) => {
              const barH = maxVolume > 0 ? (c.volume / maxVolume) * volumeH : 0;
              return (
                <rect key={`v-${c.index}`}
                  x={c.x - candleWidth / 2}
                  y={priceChartH + gapH + volumeH - barH}
                  width={candleWidth} height={barH}
                  fill={c.color}
                  fillOpacity={hoveredCandle === c.index ? '0.7' : '0.3'}
                />
              );
            })}
          </g>
        )}

        {/* RSI */}
        {showRSI && rsiData.length > 0 && (() => {
          const rsiTop = priceChartH + (showVolume ? volumeH + gapH : 0) + gapH;
          return (
            <g>
              <rect x={leftPad} y={rsiTop} width={usableWidth} height={rsiH} fill="#0d1220" fillOpacity="0.5" />
              {/* Overbought zone */}
              <rect x={leftPad} y={rsiTop} width={usableWidth} height={rsiH * 0.3} fill="#ef4444" fillOpacity="0.05" />
              {/* Oversold zone */}
              <rect x={leftPad} y={rsiTop + rsiH * 0.7} width={usableWidth} height={rsiH * 0.3} fill="#22c55e" fillOpacity="0.05" />
              {/* Reference lines */}
              <line x1={leftPad} y1={rsiTop + rsiH * 0.3} x2={usableWidth} y2={rsiTop + rsiH * 0.3} stroke="#1a1f35" strokeWidth="0.5" strokeDasharray="2,2" />
              <line x1={leftPad} y1={rsiTop + rsiH * 0.5} x2={usableWidth} y2={rsiTop + rsiH * 0.5} stroke="#1a1f35" strokeWidth="0.5" strokeDasharray="4,4" />
              <line x1={leftPad} y1={rsiTop + rsiH * 0.7} x2={usableWidth} y2={rsiTop + rsiH * 0.7} stroke="#1a1f35" strokeWidth="0.5" strokeDasharray="2,2" />
              {/* RSI line */}
              <polyline
                points={rsiData.map((rsi, i) => {
                  const x = (i / (rsiData.length - 1)) * usableWidth;
                  const y = rsiTop + rsiH - (rsi / 100) * rsiH;
                  return `${x},${y}`;
                }).join(' ')}
                fill="none" stroke="#eab308" strokeWidth="1.5"
              />
              {/* Labels */}
              <text x={5} y={rsiTop + 10} fill="#374151" fontSize="9" fontFamily="monospace">RSI</text>
              <text x={usableWidth + 5} y={rsiTop + rsiH * 0.3 + 3} fill="#374151" fontSize="8" fontFamily="monospace">70</text>
              <text x={usableWidth + 5} y={rsiTop + rsiH * 0.5 + 3} fill="#374151" fontSize="8" fontFamily="monospace">50</text>
              <text x={usableWidth + 5} y={rsiTop + rsiH * 0.7 + 3} fill="#374151" fontSize="8" fontFamily="monospace">30</text>
              {/* Current RSI value */}
              {rsiData.length > 0 && (
                <text
                  x={usableWidth + 5}
                  y={rsiTop + rsiH - (rsiData[rsiData.length - 1] / 100) * rsiH + 3}
                  fill="#eab308" fontSize="9" fontFamily="monospace" fontWeight="bold"
                >
                  {rsiData[rsiData.length - 1].toFixed(0)}
                </text>
              )}
            </g>
          );
        })()}

        {/* Time labels */}
        <g fill="#374151" fontSize="9" fontFamily="monospace">
          {timeLabels.map((l, i) => (
            <text key={`t-${i}`} x={l.x} y={totalH - 2} textAnchor="middle">{l.time}</text>
          ))}
        </g>
      </svg>
    </div>
  );
};
