import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';

interface CandleData {
  time: string;
  timestamp?: string;
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
  resolution?: string;
}

// ── Client-side indicator calculations ──

function calculateRSI(prices: number[], period: number): (number | null)[] {
  // Returns array aligned with prices (null for warmup period)
  const result: (number | null)[] = [];
  const gains: number[] = [];
  const losses: number[] = [];
  for (let i = 0; i < prices.length; i++) {
    if (i === 0) { result.push(null); continue; }
    const change = prices[i] - prices[i - 1];
    gains.push(change > 0 ? change : 0);
    losses.push(change < 0 ? Math.abs(change) : 0);
    if (gains.length < period) { result.push(null); continue; }
    if (gains.length === period) {
      const avgGain = gains.reduce((a, b) => a + b, 0) / period;
      const avgLoss = losses.reduce((a, b) => a + b, 0) / period;
      const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
      result.push(avgLoss === 0 ? 100 : 100 - (100 / (1 + rs)));
    } else {
      // Use Wilder smoothing
      const prevRsi = result[result.length - 1];
      if (prevRsi === null) { result.push(null); continue; }
      // Recalculate with smoothing
      let avgGain = gains.slice(0, period).reduce((a, b) => a + b, 0) / period;
      let avgLoss = losses.slice(0, period).reduce((a, b) => a + b, 0) / period;
      for (let j = period; j < gains.length; j++) {
        avgGain = (avgGain * (period - 1) + gains[j]) / period;
        avgLoss = (avgLoss * (period - 1) + losses[j]) / period;
      }
      const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
      result.push(avgLoss === 0 ? 100 : 100 - (100 / (1 + rs)));
    }
  }
  return result;
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
      upper.push(null); middle.push(null); lower.push(null);
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

// Trading sessions (UTC hours)
const TRADING_SESSIONS = [
  { name: 'Tokyo',  start: 0,  end: 9,  color: '#f97316', abbr: 'TKY' },
  { name: 'London', start: 7,  end: 16, color: '#3b82f6', abbr: 'LDN' },
  { name: 'NY',     start: 13, end: 22, color: '#22c55e', abbr: 'NY' },
];

function getSessionForHour(hour: number) {
  return TRADING_SESSIONS.filter(s => {
    if (s.start < s.end) return hour >= s.start && hour < s.end;
    return hour >= s.start || hour < s.end;
  });
}

/** Parse an ISO timestamp or HH:MM time string into { hour, date } */
function parseTimestamp(candle: CandleData): { hour: number; dateStr: string } | null {
  // Prefer ISO timestamp
  if (candle.timestamp) {
    try {
      const dt = new Date(candle.timestamp);
      if (!isNaN(dt.getTime())) {
        return { hour: dt.getUTCHours(), dateStr: candle.timestamp.split('T')[0] || '' };
      }
    } catch { /* fall through */ }
  }
  // Fallback: parse HH:MM from time field
  const m = candle.time.match(/^(\d{1,2}):(\d{2})/);
  if (m) return { hour: parseInt(m[1], 10), dateStr: '' };
  return null;
}

export const CandlestickChart: React.FC<CandlestickChartProps> = ({
  symbol,
  data,
  height = 300,
  showVolume = true,
  showRSI = true,
  resolution = '60',
}) => {
  const [hoveredCandle, setHoveredCandle] = useState<number | null>(null);
  const [overlays, setOverlays] = useState({
    bb: true,
    sma: true,
    macd: true,
    sessions: true,
  });
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(0);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) setContainerWidth(entry.contentRect.width);
    });
    ro.observe(el);
    setContainerWidth(el.clientWidth);
    return () => ro.disconnect();
  }, []);

  const toggleOverlay = (key: keyof typeof overlays) => {
    setOverlays(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const isDaily = resolution === 'D';

  // Validate data
  const validData = useMemo(() =>
    (data || []).filter(d =>
      d && typeof d.open === 'number' && typeof d.high === 'number' &&
      typeof d.low === 'number' && typeof d.close === 'number' &&
      typeof d.volume === 'number' && isFinite(d.open) && isFinite(d.close) &&
      d.high >= d.low
    ), [data]);

  // Compute all indicators on FULL data (including warmup candles)
  const indicators = useMemo(() => {
    if (validData.length === 0) return null;
    const closes = validData.map(d => d.close);
    return {
      rsi: calculateRSI(closes, 14),
      sma20: calculateSMA(closes, 20),
      sma50: calculateSMA(closes, 50),
      bb: calculateBollingerBands(closes, 20, 2),
      macd: calculateMACD(closes),
    };
  }, [validData]);

  // Compute session bands using timestamps (with date-awareness)
  const sessionBands = useMemo(() => {
    if (!overlays.sessions || validData.length === 0 || isDaily) return [];

    const parsed = validData.map(d => parseTimestamp(d));
    // If no valid timestamps, skip sessions
    if (parsed.every(p => p === null)) return [];

    type Band = { session: typeof TRADING_SESSIONS[0]; startIdx: number; endIdx: number };
    const bands: Band[] = [];

    for (const session of TRADING_SESSIONS) {
      let inSession = false;
      let startIdx = 0;
      let prevDate = '';
      for (let i = 0; i < parsed.length; i++) {
        const p = parsed[i];
        if (!p) {
          if (inSession) { bands.push({ session, startIdx, endIdx: i - 1 }); inSession = false; }
          continue;
        }
        const active = getSessionForHour(p.hour).some(s => s.name === session.name);
        // Break session when date changes (new day = new session band)
        const dateChanged = p.dateStr && prevDate && p.dateStr !== prevDate;
        if (dateChanged && inSession) {
          bands.push({ session, startIdx, endIdx: i - 1 });
          inSession = false;
        }
        if (active && !inSession) {
          startIdx = i;
          inSession = true;
        } else if (!active && inSession) {
          bands.push({ session, startIdx, endIdx: i - 1 });
          inSession = false;
        }
        prevDate = p.dateStr;
      }
      if (inSession) bands.push({ session, startIdx, endIdx: parsed.length - 1 });
    }
    return bands;
  }, [validData, overlays.sessions, isDaily]);

  if (!data || data.length === 0 || validData.length === 0) {
    return (
      <div className="h-full flex items-center justify-center" style={{ color: '#4a5568' }}>
        <div className="text-xs uppercase tracking-widest">No chart data</div>
      </div>
    );
  }

  if (!indicators) return null;

  const n = validData.length;
  const volumes = validData.map(d => d.volume);

  // Include BB bands in price range
  let maxPrice = Math.max(...validData.map(d => d.high));
  let minPrice = Math.min(...validData.map(d => d.low));
  if (overlays.bb) {
    for (const v of indicators.bb.upper) { if (v !== null && v > maxPrice) maxPrice = v; }
    for (const v of indicators.bb.lower) { if (v !== null && v < minPrice) minPrice = v; }
  }

  const maxVolume = Math.max(...volumes);
  const priceRange = maxPrice - minPrice || 1;

  // Layout - improved for better visibility
  const isMobile = containerWidth > 0 && containerWidth < 600;
  const showMACD = overlays.macd;
  const chartWidth = containerWidth > 0 ? Math.max(800, containerWidth) : 1100;
  const macdH = showMACD ? 50 : 0;
  const volumeH = showVolume ? 45 : 0;
  const rsiH = showRSI ? 50 : 0;
  const gapH = 8;
  const xAxisH = 25; // Height reserved for X-axis labels
  const priceChartH = Math.max(150, height - (showVolume ? volumeH + gapH : 0) - (showMACD ? macdH + gapH : 0) - (showRSI ? rsiH + gapH : 0) - xAxisH - 10);
  const totalH = priceChartH + (showVolume ? volumeH + gapH : 0) + (showMACD ? macdH + gapH : 0) + (showRSI ? rsiH + gapH : 0) + xAxisH;
  const rightPad = isMobile ? 50 : 60;
  const usableWidth = chartWidth - rightPad;

  const currentPrice = validData[n - 1].close;
  const prevClose = n > 1 ? validData[n - 2].close : currentPrice;
  const priceChange = currentPrice - prevClose;
  const priceChangeStr = `${priceChange >= 0 ? '+' : ''}${priceChange.toFixed(2)}`;

  const priceToY = (p: number) => priceChartH - ((p - minPrice) / priceRange) * priceChartH;

  // Index to x coordinate
  const idxToX = (i: number) => n > 1 ? (i / (n - 1)) * usableWidth : usableWidth / 2;

  // Price grid levels
  const priceLevels = [];
  const levelCount = 6;
  for (let i = 0; i <= levelCount; i++) {
    const price = minPrice + (priceRange * i / levelCount);
    priceLevels.push({ price, y: priceToY(price) });
  }

  // Time labels — improved for readability and no overlap
  const timeLabels: { time: string; x: number; isMajor?: boolean }[] = [];
  const maxLabels = isMobile ? 4 : 8;
  const step = Math.max(1, Math.floor(n / maxLabels));
  let prevLabelDate = '';
  for (let i = 0; i < n; i += step) {
    let label = validData[i].time;
    let isMajor = false;
    // For daily charts prefer MM/DD, for intraday prefer HH:MM with date at day boundaries
    if (validData[i].timestamp) {
      try {
        const dt = new Date(validData[i].timestamp!);
        const currentDate = validData[i].timestamp!.split('T')[0];
        if (!isNaN(dt.getTime())) {
          if (isDaily) {
            label = `${(dt.getUTCMonth() + 1).toString().padStart(2, '0')}/${dt.getUTCDate().toString().padStart(2, '0')}`;
            isMajor = true;
          } else {
            const timeStr = `${dt.getUTCHours().toString().padStart(2, '0')}:${dt.getUTCMinutes().toString().padStart(2, '0')}`;
            // Show full date+time at day boundaries or every 6 hours
            const isDayBoundary = currentDate !== prevLabelDate;
            const isMajorHour = dt.getUTCHours() % 6 === 0;
            if (isDayBoundary || isMajorHour) {
              label = `${dt.getUTCDate()}/${dt.getUTCMonth() + 1} ${timeStr}`;
              isMajor = true;
            } else {
              label = timeStr;
            }
          }
          prevLabelDate = currentDate;
        }
      } catch { /* use fallback */ }
    }
    timeLabels.push({ time: label, x: idxToX(i), isMajor });
  }

  // Candlesticks
  const candleSpacing = usableWidth / n;
  const candleWidth = Math.max(2, candleSpacing * 0.7);

  const candlesticks = validData.map((candle, index) => {
    const x = idxToX(index);
    const openY = priceToY(candle.open);
    const closeY = priceToY(candle.close);
    const highY = priceToY(candle.high);
    const lowY = priceToY(candle.low);
    const isBullish = candle.close >= candle.open;
    const rsiVal = indicators.rsi[index];

    return {
      index, x, openY, closeY, highY, lowY, isBullish,
      bodyY: Math.min(openY, closeY),
      bodyH: Math.max(1, Math.abs(closeY - openY)),
      color: isBullish ? '#22c55e' : '#ef4444',
      volume: candle.volume,
      data: candle,
      rsi: rsiVal,
    };
  });

  // Build polyline string for indicator overlay (aligned to candle indices)
  const toPolyline = (values: (number | null)[], mapY: (v: number) => number): string => {
    const pts: string[] = [];
    for (let i = 0; i < values.length; i++) {
      const v = values[i];
      if (v === null || isNaN(v)) continue;
      pts.push(`${idxToX(i)},${mapY(v)}`);
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
    const idx = Math.round((chartX / usableWidth) * (n - 1));
    if (idx >= 0 && idx < n) setHoveredCandle(idx);
  };

  const handleTouchMove = useCallback((event: React.TouchEvent<SVGElement>) => {
    if (event.touches.length !== 1) return;
    const touch = event.touches[0];
    const rect = event.currentTarget.getBoundingClientRect();
    const x = touch.clientX - rect.left;
    const chartX = (x / rect.width) * chartWidth;
    const idx = Math.round((chartX / usableWidth) * (n - 1));
    if (idx >= 0 && idx < n) setHoveredCandle(idx);
  }, [chartWidth, usableWidth, n]);

  const hoveredMacd = hoveredCandle !== null ? {
    macd: indicators.macd.macdLine[hoveredCandle],
    signal: indicators.macd.signalLine[hoveredCandle],
    hist: indicators.macd.histogram[hoveredCandle],
  } : null;

  // RSI polyline aligned to candle x-axis
  const rsiPolyline = useMemo(() => {
    const pts: string[] = [];
    for (let i = 0; i < indicators.rsi.length; i++) {
      const v = indicators.rsi[i];
      if (v === null) continue;
      const x = idxToX(i);
      const y = rsiTop + rsiH - (v / 100) * rsiH;
      pts.push(`${x},${y}`);
    }
    return pts.join(' ');
  }, [indicators.rsi, rsiTop, rsiH, usableWidth, n]);

  return (
    <div className="h-full relative" ref={containerRef}>
      {/* Header */}
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
          {(['bb', 'sma', 'macd', 'sessions'] as const).map(key => {
            const colors: Record<string, string> = { bb: '#a78bfa', sma: '#38bdf8', macd: '#fb923c', sessions: '#94a3b8' };
            const labels: Record<string, string> = { bb: 'BB', sma: 'SMA', macd: 'MACD', sessions: 'SESS' };
            const c = colors[key];
            return (
              <button key={key} onClick={() => toggleOverlay(key)}
                className="px-1 sm:px-1.5 py-0.5 text-[8px] sm:text-[9px] font-medium rounded-sm transition-all"
                style={{
                  color: overlays[key] ? c : '#374151',
                  backgroundColor: overlays[key] ? '#1a1f35' : 'transparent',
                  border: `1px solid ${overlays[key] ? c + '33' : '#1a1f35'}`,
                }}
              >{labels[key]}</button>
            );
          })}
        </div>

        {/* Hover info */}
        {hoveredCandle !== null && candlesticks[hoveredCandle] && (
          <div className="flex flex-wrap items-center gap-1 sm:gap-2 ml-auto text-[9px] sm:text-[10px]" style={{ color: '#64748b' }}>
            {(() => {
              const candle = candlesticks[hoveredCandle].data;
              let dateStr = '';
              if (candle.timestamp) {
                try {
                  const dt = new Date(candle.timestamp);
                  if (!isNaN(dt.getTime())) {
                    const day = dt.getUTCDate().toString().padStart(2, '0');
                    const month = (dt.getUTCMonth() + 1).toString().padStart(2, '0');
                    const hours = dt.getUTCHours().toString().padStart(2, '0');
                    const minutes = dt.getUTCMinutes().toString().padStart(2, '0');
                    dateStr = `${day}/${month} ${hours}:${minutes}`;
                  }
                } catch {}
              }
              if (!dateStr && candle.time) {
                dateStr = candle.time;
              }
              return <span style={{ color: '#94a3b8', fontWeight: 'bold' }}>{dateStr}</span>;
            })()}
            <span>O:{candlesticks[hoveredCandle].data.open.toFixed(2)}</span>
            <span>H:{candlesticks[hoveredCandle].data.high.toFixed(2)}</span>
            <span>L:{candlesticks[hoveredCandle].data.low.toFixed(2)}</span>
            <span>C:{candlesticks[hoveredCandle].data.close.toFixed(2)}</span>
            <span className="hidden sm:inline">V:{(candlesticks[hoveredCandle].data.volume / 1000).toFixed(0)}K</span>
            {candlesticks[hoveredCandle].rsi != null && (
              <span className="hidden sm:inline">RSI:{candlesticks[hoveredCandle].rsi!.toFixed(1)}</span>
            )}
            {overlays.macd && hoveredMacd?.macd != null && (
              <span className="hidden sm:inline" style={{ color: '#fb923c' }}>MACD:{hoveredMacd.macd.toFixed(2)}</span>
            )}
          </div>
        )}
      </div>

      {/* Scrollable chart */}
      <div className="overflow-x-auto" style={{ WebkitOverflowScrolling: 'touch' }}>
        <svg
          width={isMobile ? chartWidth : (containerWidth > 0 ? containerWidth : chartWidth)}
          height={height}
          viewBox={`0 0 ${chartWidth} ${totalH}`}
          preserveAspectRatio="xMidYMid meet"
          onMouseMove={handleMouseMove}
          onMouseLeave={() => setHoveredCandle(null)}
          onTouchMove={handleTouchMove}
          onTouchEnd={() => setHoveredCandle(null)}
          style={{ cursor: 'crosshair', minWidth: `${chartWidth}px` }}
        >
        {/* ── Session Background Bands ── */}
        {overlays.sessions && sessionBands.length > 0 && (
          <g>
            {sessionBands.map((band, i) => {
              const x1 = idxToX(band.startIdx);
              const x2 = idxToX(band.endIdx);
              const w = Math.max(x2 - x1, 2);
              return (
                <g key={`sess-${i}`}>
                  <rect x={x1} y={0} width={w} height={priceChartH}
                    fill={band.session.color} fillOpacity="0.04" />
                  <line x1={x1} y1={0} x2={x1} y2={priceChartH}
                    stroke={band.session.color} strokeWidth="0.5" strokeDasharray="3,3" opacity="0.3" />
                  <text x={x1 + 3} y={10}
                    fill={band.session.color} fontSize="7" fontFamily="monospace" opacity="0.5">
                    {band.session.abbr}
                  </text>
                </g>
              );
            })}
          </g>
        )}

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

        {/* ── Bollinger Bands ── */}
        {overlays.bb && (
          <g>
            <path
              d={(() => {
                const upperPts: string[] = [];
                const lowerPts: string[] = [];
                for (let i = 0; i < n; i++) {
                  const u = indicators.bb.upper[i];
                  const l = indicators.bb.lower[i];
                  if (u === null || l === null) continue;
                  const x = idxToX(i);
                  upperPts.push(`${x},${priceToY(u)}`);
                  lowerPts.unshift(`${x},${priceToY(l)}`);
                }
                if (upperPts.length === 0) return '';
                return `M${upperPts.join(' L')} L${lowerPts.join(' L')}Z`;
              })()}
              fill="#a78bfa" fillOpacity="0.06"
            />
            <polyline points={toPolyline(indicators.bb.upper, priceToY)}
              fill="none" stroke="#a78bfa" strokeWidth="0.8" strokeDasharray="3,2" opacity="0.6" />
            <polyline points={toPolyline(indicators.bb.middle, priceToY)}
              fill="none" stroke="#a78bfa" strokeWidth="0.6" opacity="0.4" />
            <polyline points={toPolyline(indicators.bb.lower, priceToY)}
              fill="none" stroke="#a78bfa" strokeWidth="0.8" strokeDasharray="3,2" opacity="0.6" />
          </g>
        )}

        {/* ── SMA Lines ── */}
        {overlays.sma && (
          <g>
            <polyline points={toPolyline(indicators.sma20, priceToY)}
              fill="none" stroke="#38bdf8" strokeWidth="1" opacity="0.7" />
            <polyline points={toPolyline(indicators.sma50, priceToY)}
              fill="none" stroke="#f472b6" strokeWidth="1" opacity="0.7" />
            <text x={usableWidth + 5} y={12} fill="#38bdf8" fontSize="8" fontFamily="monospace" opacity="0.7">SMA20</text>
            <text x={usableWidth + 5} y={22} fill="#f472b6" fontSize="8" fontFamily="monospace" opacity="0.7">SMA50</text>
          </g>
        )}

        {/* Current Price Line */}
        <line x1={0} y1={priceToY(currentPrice)} x2={usableWidth} y2={priceToY(currentPrice)}
          stroke={priceChange >= 0 ? '#22c55e' : '#ef4444'} strokeWidth="0.5" strokeDasharray="3,3" opacity="0.6" />
        <text x={usableWidth + 5} y={priceToY(currentPrice) + 3}
          fill={priceChange >= 0 ? '#22c55e' : '#ef4444'} fontSize="10" fontFamily="monospace" fontWeight="bold">
          {currentPrice.toFixed(2)}
        </text>

        {/* ── Candlesticks ── */}
        <g>
          {candlesticks.map((c) => (
            <g key={`c-${c.index}`}>
              <line x1={c.x} y1={c.highY} x2={c.x} y2={c.lowY}
                stroke={c.color} strokeWidth={hoveredCandle === c.index ? '1' : '0.5'}
                opacity={hoveredCandle === null || hoveredCandle === c.index ? '1' : '0.5'} />
              <rect
                x={c.x - candleWidth / 2} y={c.bodyY} width={candleWidth} height={Math.max(1, c.bodyH)}
                fill={c.color} stroke={c.color} strokeWidth="0.3"
                opacity={hoveredCandle === null || hoveredCandle === c.index ? '1' : '0.5'} />
            </g>
          ))}
        </g>

        {/* Hover crosshair */}
        {hoveredCandle !== null && candlesticks[hoveredCandle] && (
          <line
            x1={candlesticks[hoveredCandle].x} y1={0}
            x2={candlesticks[hoveredCandle].x} y2={totalH - 20}
            stroke="#374151" strokeWidth="0.5" strokeDasharray="2,2" />
        )}

        {/* ── Volume ── */}
        {showVolume && (
          <g>
            <text x={5} y={volumeTop + 10} fill="#374151" fontSize="9" fontFamily="monospace">VOL</text>
            {candlesticks.map((c) => {
              const barH = maxVolume > 0 ? (c.volume / maxVolume) * volumeH : 0;
              return (
                <rect key={`v-${c.index}`}
                  x={c.x - candleWidth / 2} y={volumeTop + volumeH - barH}
                  width={candleWidth} height={barH}
                  fill={c.color} fillOpacity={hoveredCandle === c.index ? '0.7' : '0.3'} />
              );
            })}
          </g>
        )}

        {/* ── MACD Panel ── */}
        {showMACD && macdVals.length > 0 && (
          <g>
            <rect x={0} y={macdTop} width={usableWidth} height={macdH} fill="#0d1220" fillOpacity="0.5" />
            <line x1={0} y1={macdTop + macdH / 2} x2={usableWidth} y2={macdTop + macdH / 2}
              stroke="#1a1f35" strokeWidth="0.5" />
            {validData.map((_, i) => {
              const h = indicators.macd.histogram[i];
              if (h === null) return null;
              const x = idxToX(i);
              const barH = Math.abs(h / (macdMax || 1)) * (macdH / 2 - 2);
              const barColor = h >= 0 ? '#22c55e' : '#ef4444';
              return (
                <rect key={`mh-${i}`}
                  x={x - candleWidth / 2}
                  y={h >= 0 ? macdToY(h) : macdTop + macdH / 2}
                  width={candleWidth} height={Math.max(0.5, barH)}
                  fill={barColor} fillOpacity="0.5" />
              );
            })}
            <polyline points={toPolyline(indicators.macd.macdLine, macdToY)}
              fill="none" stroke="#38bdf8" strokeWidth="1" />
            <polyline points={toPolyline(indicators.macd.signalLine, macdToY)}
              fill="none" stroke="#fb923c" strokeWidth="1" strokeDasharray="2,1" />
            <text x={5} y={macdTop + 10} fill="#374151" fontSize="9" fontFamily="monospace">MACD</text>
            <text x={usableWidth + 5} y={macdTop + 10} fill="#38bdf8" fontSize="7" fontFamily="monospace">MACD</text>
            <text x={usableWidth + 5} y={macdTop + 19} fill="#fb923c" fontSize="7" fontFamily="monospace">Signal</text>
          </g>
        )}

        {/* ── RSI Panel ── */}
        {showRSI && indicators.rsi.some(v => v !== null) && (
          <g>
            <rect x={0} y={rsiTop} width={usableWidth} height={rsiH} fill="#0d1220" fillOpacity="0.5" />
            <rect x={0} y={rsiTop} width={usableWidth} height={rsiH * 0.3} fill="#ef4444" fillOpacity="0.05" />
            <rect x={0} y={rsiTop + rsiH * 0.7} width={usableWidth} height={rsiH * 0.3} fill="#22c55e" fillOpacity="0.05" />
            <line x1={0} y1={rsiTop + rsiH * 0.3} x2={usableWidth} y2={rsiTop + rsiH * 0.3} stroke="#1a1f35" strokeWidth="0.5" strokeDasharray="2,2" />
            <line x1={0} y1={rsiTop + rsiH * 0.5} x2={usableWidth} y2={rsiTop + rsiH * 0.5} stroke="#1a1f35" strokeWidth="0.5" strokeDasharray="4,4" />
            <line x1={0} y1={rsiTop + rsiH * 0.7} x2={usableWidth} y2={rsiTop + rsiH * 0.7} stroke="#1a1f35" strokeWidth="0.5" strokeDasharray="2,2" />
            {/* RSI line — aligned to candle x-axis */}
            <polyline points={rsiPolyline} fill="none" stroke="#eab308" strokeWidth="1.5" />
            <text x={5} y={rsiTop + 10} fill="#374151" fontSize="9" fontFamily="monospace">RSI</text>
            <text x={usableWidth + 5} y={rsiTop + rsiH * 0.3 + 3} fill="#374151" fontSize="8" fontFamily="monospace">70</text>
            <text x={usableWidth + 5} y={rsiTop + rsiH * 0.5 + 3} fill="#374151" fontSize="8" fontFamily="monospace">50</text>
            <text x={usableWidth + 5} y={rsiTop + rsiH * 0.7 + 3} fill="#374151" fontSize="8" fontFamily="monospace">30</text>
            {/* Current RSI value */}
            {(() => {
              const lastRsi = [...indicators.rsi].reverse().find(v => v !== null);
              if (lastRsi == null) return null;
              return (
                <text x={usableWidth + 5}
                  y={rsiTop + rsiH - (lastRsi / 100) * rsiH + 3}
                  fill="#eab308" fontSize="9" fontFamily="monospace" fontWeight="bold">
                  {lastRsi.toFixed(0)}
                </text>
              );
            })()}
          </g>
        )}

        {/* ── Time labels ── */}
        <g fontFamily="monospace">
          {timeLabels.map((l, i) => (
            <text 
              key={`t-${i}`} 
              x={l.x} 
              y={totalH - 5} 
              textAnchor="middle"
              fill={l.isMajor ? '#94a3b8' : '#475569'}
              fontSize={l.isMajor ? '10' : '8'}
              fontWeight={l.isMajor ? 'bold' : 'normal'}
            >{l.time}</text>
          ))}
        </g>
        {/* X-axis line */}
        <line x1={0} y1={totalH - xAxisH + 5} x2={usableWidth} y2={totalH - xAxisH + 5} stroke="#1e293b" strokeWidth="1" />
        </svg>
      </div>
    </div>
  );
};
