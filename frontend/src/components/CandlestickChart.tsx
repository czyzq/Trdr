import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';

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

// ── Client-side indicator calculations ──

function calculateRSI(prices: number[], period: number): number[] {
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
}

function calculateSMA(prices: number[], period: number): (number | null)[] {
  return prices.map((_, i) => {
    if (i < period - 1) return null;
    const slice = prices.slice(i - period + 1, i + 1);
    return slice.reduce((a, b) => a + b, 0) / period;
  });
}

function calculateEMA(prices: number[], period: number): number[] {
  if (prices.length < period) return [];
  const multiplier = 2 / (period + 1);
  const ema: number[] = [];
  let val = prices.slice(0, period).reduce((a, b) => a + b, 0) / period;
  // Fill leading nulls
  for (let i = 0; i < period - 1; i++) ema.push(NaN);
  ema.push(val);
  for (let i = period; i < prices.length; i++) {
    val = (prices[i] - val) * multiplier + val;
    ema.push(val);
  }
  return ema;
}

function calculateBollingerBands(prices: number[], period: number = 20, stdDevMult: number = 2) {
  const upper: (number | null)[] = [];
  const middle: (number | null)[] = [];
  const lower: (number | null)[] = [];

  for (let i = 0; i < prices.length; i++) {
    if (i < period - 1) {
      upper.push(null);
      middle.push(null);
      lower.push(null);
      continue;
    }
    const slice = prices.slice(i - period + 1, i + 1);
    const mean = slice.reduce((a, b) => a + b, 0) / period;
    const variance = slice.reduce((sum, p) => sum + (p - mean) ** 2, 0) / period;
    const std = Math.sqrt(variance);
    upper.push(mean + stdDevMult * std);
    middle.push(mean);
    lower.push(mean - stdDevMult * std);
  }
  return { upper, middle, lower };
}

function calculateMACD(prices: number[], fast = 12, slow = 26, signal = 9) {
  const emaFast = calculateEMA(prices, fast);
  const emaSlow = calculateEMA(prices, slow);

  const macdLine: (number | null)[] = [];
  for (let i = 0; i < prices.length; i++) {
    if (isNaN(emaFast[i]) || isNaN(emaSlow[i])) {
      macdLine.push(null);
    } else {
      macdLine.push(emaFast[i] - emaSlow[i]);
    }
  }

  // Signal line = EMA of MACD line (ignoring nulls)
  const validMacd = macdLine.filter((v): v is number => v !== null);
  const signalEma = calculateEMA(validMacd, signal);

  const signalLine: (number | null)[] = [];
  const histogram: (number | null)[] = [];
  let validIdx = 0;
  for (let i = 0; i < prices.length; i++) {
    if (macdLine[i] === null) {
      signalLine.push(null);
      histogram.push(null);
    } else {
      const sig = isNaN(signalEma[validIdx]) ? null : signalEma[validIdx];
      signalLine.push(sig);
      histogram.push(sig !== null ? macdLine[i]! - sig : null);
      validIdx++;
    }
  }

  return { macdLine, signalLine, histogram };
}

export const CandlestickChart: React.FC<CandlestickChartProps> = ({
  symbol,
  data,
  height = 300,
  showVolume = true,
  showRSI = true,
}) => {
  const [hoveredCandle, setHoveredCandle] = useState<number | null>(null);
  const [overlays, setOverlays] = useState({
    bb: true,
    sma: true,
    macd: true,
  });
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(0);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setContainerWidth(entry.contentRect.width);
      }
    });
    ro.observe(el);
    setContainerWidth(el.clientWidth);
    return () => ro.disconnect();
  }, []);

  const toggleOverlay = (key: keyof typeof overlays) => {
    setOverlays(prev => ({ ...prev, [key]: !prev[key] }));
  };

  // Validate data
  const validData = useMemo(() =>
    (data || []).filter(d =>
      d && typeof d.open === 'number' && typeof d.high === 'number' &&
      typeof d.low === 'number' && typeof d.close === 'number' &&
      typeof d.volume === 'number' && isFinite(d.open) && isFinite(d.close) &&
      d.high >= d.low
    ), [data]);

  // Compute all indicators
  const indicators = useMemo(() => {
    if (validData.length === 0) return null;
    const closes = validData.map(d => d.close);
    return {
      rsi: closes.length >= 14 ? calculateRSI(closes, 14) : [],
      sma20: calculateSMA(closes, 20),
      sma50: calculateSMA(closes, 50),
      bb: calculateBollingerBands(closes, 20, 2),
      macd: calculateMACD(closes),
    };
  }, [validData]);

  if (!data || data.length === 0 || validData.length === 0) {
    return (
      <div className="h-full flex items-center justify-center" style={{ color: '#4a5568' }}>
        <div className="text-xs uppercase tracking-widest">No chart data</div>
      </div>
    );
  }

  if (!indicators) return null;

  const prices = validData.map(d => d.close);
  const volumes = validData.map(d => d.volume);

  // Include BB bands in price range calculation when BB overlay is on
  let maxPrice = Math.max(...validData.map(d => d.high));
  let minPrice = Math.min(...validData.map(d => d.low));
  if (overlays.bb) {
    for (const v of indicators.bb.upper) {
      if (v !== null && v > maxPrice) maxPrice = v;
    }
    for (const v of indicators.bb.lower) {
      if (v !== null && v < minPrice) minPrice = v;
    }
  }

  const maxVolume = Math.max(...volumes);
  const priceRange = maxPrice - minPrice || 1;

  // Layout — responsive: use container width on mobile, 1100 on desktop
  const isMobile = containerWidth > 0 && containerWidth < 600;
  const showMACD = overlays.macd;
  // On mobile, set chart width to at least 600 for readability (scrollable)
  const chartWidth = containerWidth > 0
    ? Math.max(600, containerWidth)
    : 1100;
  const macdH = showMACD ? 45 : 0;
  const volumeH = showVolume ? 35 : 0;
  const rsiH = showRSI ? 45 : 0;
  const gapH = 6;
  const headerH = 0;
  // Price chart takes remaining space
  const priceChartH = Math.max(120,
    (showMACD ? 180 : 220)
    - (showVolume ? 0 : -30)
    - (showRSI ? 0 : -30)
  );
  const totalH = priceChartH
    + (showVolume ? volumeH + gapH : 0)
    + (showMACD ? macdH + gapH : 0)
    + (showRSI ? rsiH + gapH : 0)
    + 20; // time labels
  const rightPad = isMobile ? 45 : 55;
  const usableWidth = chartWidth - rightPad;

  const currentPrice = validData[validData.length - 1].close;
  const prevClose = validData.length > 1 ? validData[validData.length - 2].close : currentPrice;
  const priceChange = currentPrice - prevClose;
  const priceChangeStr = `${priceChange >= 0 ? '+' : ''}${priceChange.toFixed(2)}`;

  // Helper: map price to Y in price chart area
  const priceToY = (p: number) => priceChartH - ((p - minPrice) / priceRange) * priceChartH;

  // Price levels
  const priceLevels = [];
  const levelCount = 6;
  for (let i = 0; i <= levelCount; i++) {
    const price = minPrice + (priceRange * i / levelCount);
    priceLevels.push({ price, y: priceToY(price) });
  }

  // Time labels — fewer on mobile to avoid overlap
  const timeLabels: { time: string; x: number }[] = [];
  const maxLabels = isMobile ? 6 : 10;
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
    const openY = priceToY(candle.open);
    const closeY = priceToY(candle.close);
    const highY = priceToY(candle.high);
    const lowY = priceToY(candle.low);
    const isBullish = candle.close >= candle.open;

    return {
      index, x, openY, closeY, highY, lowY, isBullish,
      bodyY: Math.min(openY, closeY),
      bodyH: Math.max(1, Math.abs(closeY - openY)),
      color: isBullish ? '#22c55e' : '#ef4444',
      volume: candle.volume,
      data: candle,
      rsi: indicators.rsi[index - 14],
    };
  });

  // Build polyline strings for overlays
  const toPolyline = (values: (number | null)[], mapY: (v: number) => number): string => {
    const pts: string[] = [];
    for (let i = 0; i < values.length; i++) {
      const v = values[i];
      if (v === null || isNaN(v)) continue;
      const x = (i / (validData.length - 1)) * usableWidth;
      pts.push(`${x},${mapY(v)}`);
    }
    return pts.join(' ');
  };

  // Section Y offsets
  let nextY = priceChartH;
  const volumeTop = nextY + gapH;
  nextY = showVolume ? volumeTop + volumeH : nextY;
  const macdTop = nextY + gapH;
  nextY = showMACD ? macdTop + macdH : nextY;
  const rsiTop = nextY + gapH;

  // MACD scaling
  const macdVals = indicators.macd.histogram.filter((v): v is number => v !== null);
  const macdLineVals = indicators.macd.macdLine.filter((v): v is number => v !== null);
  const macdSignalVals = indicators.macd.signalLine.filter((v): v is number => v !== null);
  const allMacdVals = [...macdVals, ...macdLineVals, ...macdSignalVals];
  const macdMax = allMacdVals.length > 0 ? Math.max(...allMacdVals.map(Math.abs)) : 1;
  const macdToY = (v: number) => macdTop + macdH / 2 - (v / (macdMax || 1)) * (macdH / 2 - 2);

  const handleMouseMove = (event: React.MouseEvent<SVGElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const chartX = (x / rect.width) * chartWidth;
    const idx = Math.round((chartX / usableWidth) * (candlesticks.length - 1));
    if (idx >= 0 && idx < candlesticks.length) setHoveredCandle(idx);
  };

  const handleTouchMove = useCallback((event: React.TouchEvent<SVGElement>) => {
    if (event.touches.length !== 1) return;
    const touch = event.touches[0];
    const rect = event.currentTarget.getBoundingClientRect();
    const x = touch.clientX - rect.left;
    const chartX = (x / rect.width) * chartWidth;
    const idx = Math.round((chartX / usableWidth) * (candlesticks.length - 1));
    if (idx >= 0 && idx < candlesticks.length) setHoveredCandle(idx);
  }, [chartWidth, usableWidth, candlesticks.length]);

  // Hovered MACD values
  const hoveredMacd = hoveredCandle !== null ? {
    macd: indicators.macd.macdLine[hoveredCandle],
    signal: indicators.macd.signalLine[hoveredCandle],
    hist: indicators.macd.histogram[hoveredCandle],
  } : null;

  return (
    <div className="h-full relative" ref={containerRef}>
      {/* Header: Price Info + Overlay Toggles */}
      <div className="flex flex-wrap items-center gap-1 sm:gap-3 mb-1 px-1">
        <span className="text-xs sm:text-sm font-bold" style={{ color: '#e2e8f0' }}>{symbol}</span>
        <span className="text-xs sm:text-sm font-bold" style={{ color: priceChange >= 0 ? '#22c55e' : '#ef4444' }}>
          {currentPrice.toFixed(2)}
        </span>
        <span className="text-[9px] sm:text-[10px]" style={{ color: priceChange >= 0 ? '#22c55e' : '#ef4444' }}>
          {priceChangeStr}
        </span>

        {/* Overlay toggles */}
        <div className="flex items-center gap-1 ml-1 sm:ml-2">
          <button
            onClick={() => toggleOverlay('bb')}
            className="px-1 sm:px-1.5 py-0.5 text-[8px] sm:text-[9px] font-medium rounded-sm transition-all"
            style={{
              color: overlays.bb ? '#a78bfa' : '#374151',
              backgroundColor: overlays.bb ? '#1a1f35' : 'transparent',
              border: `1px solid ${overlays.bb ? '#a78bfa33' : '#1a1f35'}`,
            }}
          >
            BB
          </button>
          <button
            onClick={() => toggleOverlay('sma')}
            className="px-1 sm:px-1.5 py-0.5 text-[8px] sm:text-[9px] font-medium rounded-sm transition-all"
            style={{
              color: overlays.sma ? '#38bdf8' : '#374151',
              backgroundColor: overlays.sma ? '#1a1f35' : 'transparent',
              border: `1px solid ${overlays.sma ? '#38bdf833' : '#1a1f35'}`,
            }}
          >
            SMA
          </button>
          <button
            onClick={() => toggleOverlay('macd')}
            className="px-1 sm:px-1.5 py-0.5 text-[8px] sm:text-[9px] font-medium rounded-sm transition-all"
            style={{
              color: overlays.macd ? '#fb923c' : '#374151',
              backgroundColor: overlays.macd ? '#1a1f35' : 'transparent',
              border: `1px solid ${overlays.macd ? '#fb923c33' : '#1a1f35'}`,
            }}
          >
            MACD
          </button>
        </div>

        {/* Hover info — wraps on mobile, inline on desktop */}
        {hoveredCandle !== null && candlesticks[hoveredCandle] && (
          <div className="flex flex-wrap items-center gap-1 sm:gap-2 ml-auto text-[9px] sm:text-[10px]" style={{ color: '#64748b' }}>
            <span>O:{candlesticks[hoveredCandle].data.open.toFixed(2)}</span>
            <span>H:{candlesticks[hoveredCandle].data.high.toFixed(2)}</span>
            <span>L:{candlesticks[hoveredCandle].data.low.toFixed(2)}</span>
            <span>C:{candlesticks[hoveredCandle].data.close.toFixed(2)}</span>
            <span className="hidden sm:inline">V:{(candlesticks[hoveredCandle].data.volume / 1000).toFixed(0)}K</span>
            {candlesticks[hoveredCandle].rsi !== undefined && (
              <span className="hidden sm:inline">RSI:{candlesticks[hoveredCandle].rsi.toFixed(1)}</span>
            )}
            {overlays.macd && hoveredMacd?.macd !== null && hoveredMacd?.macd !== undefined && (
              <span className="hidden sm:inline" style={{ color: '#fb923c' }}>MACD:{hoveredMacd.macd.toFixed(2)}</span>
            )}
          </div>
        )}
      </div>

      {/* Scrollable chart container for mobile */}
      <div
        className="overflow-x-auto"
        style={{ WebkitOverflowScrolling: 'touch' }}
      >
        <svg
          width={isMobile ? chartWidth : '100%'}
          height={height}
          viewBox={`0 0 ${chartWidth} ${totalH}`}
          preserveAspectRatio="xMidYMid meet"
          onMouseMove={handleMouseMove}
          onMouseLeave={() => setHoveredCandle(null)}
          onTouchMove={handleTouchMove}
          onTouchEnd={() => setHoveredCandle(null)}
          style={{ cursor: 'crosshair', minWidth: isMobile ? `${chartWidth}px` : undefined }}
        >
        {/* ── Price Chart Grid ── */}
        <g stroke="#131825" strokeWidth="1">
          {priceLevels.map((l, i) => (
            <line key={`g-${i}`} x1={0} y1={l.y} x2={usableWidth} y2={l.y} />
          ))}
        </g>

        {/* Price labels */}
        <g fill="#374151" fontSize="10" fontFamily="monospace">
          {priceLevels.map((l, i) => (
            <text key={`p-${i}`} x={usableWidth + 5} y={l.y + 3} textAnchor="start">
              {l.price.toFixed(l.price > 100 ? 0 : 2)}
            </text>
          ))}
        </g>

        {/* ── Bollinger Bands Overlay ── */}
        {overlays.bb && (
          <g>
            {/* Filled area between upper and lower bands */}
            <path
              d={(() => {
                const upperPts: string[] = [];
                const lowerPts: string[] = [];
                for (let i = 0; i < validData.length; i++) {
                  const u = indicators.bb.upper[i];
                  const l = indicators.bb.lower[i];
                  if (u === null || l === null) continue;
                  const x = (i / (validData.length - 1)) * usableWidth;
                  upperPts.push(`${x},${priceToY(u)}`);
                  lowerPts.unshift(`${x},${priceToY(l)}`);
                }
                if (upperPts.length === 0) return '';
                return `M${upperPts.join(' L')} L${lowerPts.join(' L')}Z`;
              })()}
              fill="#a78bfa"
              fillOpacity="0.06"
            />
            {/* Upper band */}
            <polyline
              points={toPolyline(indicators.bb.upper, priceToY)}
              fill="none" stroke="#a78bfa" strokeWidth="0.8" strokeDasharray="3,2" opacity="0.6"
            />
            {/* Middle band (SMA 20) */}
            <polyline
              points={toPolyline(indicators.bb.middle, priceToY)}
              fill="none" stroke="#a78bfa" strokeWidth="0.6" opacity="0.4"
            />
            {/* Lower band */}
            <polyline
              points={toPolyline(indicators.bb.lower, priceToY)}
              fill="none" stroke="#a78bfa" strokeWidth="0.8" strokeDasharray="3,2" opacity="0.6"
            />
          </g>
        )}

        {/* ── SMA 20/50 Lines ── */}
        {overlays.sma && (
          <g>
            <polyline
              points={toPolyline(indicators.sma20, priceToY)}
              fill="none" stroke="#38bdf8" strokeWidth="1" opacity="0.7"
            />
            <polyline
              points={toPolyline(indicators.sma50, priceToY)}
              fill="none" stroke="#f472b6" strokeWidth="1" opacity="0.7"
            />
            {/* Legend */}
            <text x={usableWidth + 5} y={12} fill="#38bdf8" fontSize="8" fontFamily="monospace" opacity="0.7">SMA20</text>
            <text x={usableWidth + 5} y={22} fill="#f472b6" fontSize="8" fontFamily="monospace" opacity="0.7">SMA50</text>
          </g>
        )}

        {/* Current Price Line */}
        <line
          x1={0} y1={priceToY(currentPrice)}
          x2={usableWidth} y2={priceToY(currentPrice)}
          stroke={priceChange >= 0 ? '#22c55e' : '#ef4444'}
          strokeWidth="0.5" strokeDasharray="3,3" opacity="0.6"
        />
        <text
          x={usableWidth + 5} y={priceToY(currentPrice) + 3}
          fill={priceChange >= 0 ? '#22c55e' : '#ef4444'}
          fontSize="10" fontFamily="monospace" fontWeight="bold"
        >
          {currentPrice.toFixed(2)}
        </text>

        {/* ── Candlesticks ── */}
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
            x2={candlesticks[hoveredCandle].x} y2={totalH - 20}
            stroke="#374151" strokeWidth="0.5" strokeDasharray="2,2"
          />
        )}

        {/* ── Volume ── */}
        {showVolume && (
          <g>
            <text x={5} y={volumeTop + 10} fill="#374151" fontSize="9" fontFamily="monospace">VOL</text>
            {candlesticks.map((c) => {
              const barH = maxVolume > 0 ? (c.volume / maxVolume) * volumeH : 0;
              return (
                <rect key={`v-${c.index}`}
                  x={c.x - candleWidth / 2}
                  y={volumeTop + volumeH - barH}
                  width={candleWidth} height={barH}
                  fill={c.color}
                  fillOpacity={hoveredCandle === c.index ? '0.7' : '0.3'}
                />
              );
            })}
          </g>
        )}

        {/* ── MACD Panel ── */}
        {showMACD && macdVals.length > 0 && (
          <g>
            <rect x={0} y={macdTop} width={usableWidth} height={macdH} fill="#0d1220" fillOpacity="0.5" />
            {/* Zero line */}
            <line
              x1={0} y1={macdTop + macdH / 2}
              x2={usableWidth} y2={macdTop + macdH / 2}
              stroke="#1a1f35" strokeWidth="0.5"
            />
            {/* Histogram bars */}
            {validData.map((_, i) => {
              const h = indicators.macd.histogram[i];
              if (h === null) return null;
              const x = (i / (validData.length - 1)) * usableWidth;
              const barH = Math.abs(h / (macdMax || 1)) * (macdH / 2 - 2);
              const barColor = h >= 0 ? '#22c55e' : '#ef4444';
              return (
                <rect key={`mh-${i}`}
                  x={x - candleWidth / 2}
                  y={h >= 0 ? macdToY(h) : macdTop + macdH / 2}
                  width={candleWidth}
                  height={Math.max(0.5, barH)}
                  fill={barColor}
                  fillOpacity="0.5"
                />
              );
            })}
            {/* MACD line */}
            <polyline
              points={toPolyline(indicators.macd.macdLine, macdToY)}
              fill="none" stroke="#38bdf8" strokeWidth="1"
            />
            {/* Signal line */}
            <polyline
              points={toPolyline(indicators.macd.signalLine, macdToY)}
              fill="none" stroke="#fb923c" strokeWidth="1" strokeDasharray="2,1"
            />
            {/* Labels */}
            <text x={5} y={macdTop + 10} fill="#374151" fontSize="9" fontFamily="monospace">MACD</text>
            <text x={usableWidth + 5} y={macdTop + 10} fill="#38bdf8" fontSize="7" fontFamily="monospace">MACD</text>
            <text x={usableWidth + 5} y={macdTop + 19} fill="#fb923c" fontSize="7" fontFamily="monospace">Signal</text>
          </g>
        )}

        {/* ── RSI Panel ── */}
        {showRSI && indicators.rsi.length > 0 && (
          <g>
            <rect x={0} y={rsiTop} width={usableWidth} height={rsiH} fill="#0d1220" fillOpacity="0.5" />
            {/* Overbought zone */}
            <rect x={0} y={rsiTop} width={usableWidth} height={rsiH * 0.3} fill="#ef4444" fillOpacity="0.05" />
            {/* Oversold zone */}
            <rect x={0} y={rsiTop + rsiH * 0.7} width={usableWidth} height={rsiH * 0.3} fill="#22c55e" fillOpacity="0.05" />
            {/* Reference lines */}
            <line x1={0} y1={rsiTop + rsiH * 0.3} x2={usableWidth} y2={rsiTop + rsiH * 0.3} stroke="#1a1f35" strokeWidth="0.5" strokeDasharray="2,2" />
            <line x1={0} y1={rsiTop + rsiH * 0.5} x2={usableWidth} y2={rsiTop + rsiH * 0.5} stroke="#1a1f35" strokeWidth="0.5" strokeDasharray="4,4" />
            <line x1={0} y1={rsiTop + rsiH * 0.7} x2={usableWidth} y2={rsiTop + rsiH * 0.7} stroke="#1a1f35" strokeWidth="0.5" strokeDasharray="2,2" />
            {/* RSI line */}
            <polyline
              points={indicators.rsi.map((rsi, i) => {
                const x = (i / (indicators.rsi.length - 1)) * usableWidth;
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
            {indicators.rsi.length > 0 && (
              <text
                x={usableWidth + 5}
                y={rsiTop + rsiH - (indicators.rsi[indicators.rsi.length - 1] / 100) * rsiH + 3}
                fill="#eab308" fontSize="9" fontFamily="monospace" fontWeight="bold"
              >
                {indicators.rsi[indicators.rsi.length - 1].toFixed(0)}
              </text>
            )}
          </g>
        )}

        {/* ── Time labels ── */}
        <g fill="#374151" fontSize="9" fontFamily="monospace">
          {timeLabels.map((l, i) => (
            <text key={`t-${i}`} x={l.x} y={totalH - 2} textAnchor="middle">{l.time}</text>
          ))}
        </g>
        </svg>
      </div>
    </div>
  );
};
