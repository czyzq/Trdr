import React from 'react';

interface SimpleChartProps {
  symbol: string;
  data?: { time: string; price: number }[];
}

const mockData = [
  { time: '09:00', price: 2050.50 },
  { time: '10:00', price: 2052.75 },
  { time: '11:00', price: 2048.25 },
  { time: '12:00', price: 2055.00 },
  { time: '13:00', price: 2061.50 },
  { time: '14:00', price: 2058.75 },
  { time: '15:00', price: 2065.25 },
  { time: '16:00', price: 2062.00 },
];

export const SimpleChart: React.FC<SimpleChartProps> = ({ symbol, data = mockData }) => {
  const maxPrice = Math.max(...data.map(d => d.price));
  const minPrice = Math.min(...data.map(d => d.price));
  const priceRange = maxPrice - minPrice;

  const points = data.map((point, index) => {
    const x = (index / (data.length - 1)) * 100;
    const y = 100 - ((point.price - minPrice) / priceRange) * 80 + 10;
    return `${x},${y}`;
  }).join(' ');

  return (
    <div className="border rounded-sm p-4" style={{ backgroundColor: '#0a0e27', borderColor: '#00ff41' }}>
      <div className="font-mono text-xs uppercase tracking-widest font-bold mb-3" style={{ color: '#00ff41' }}>
        {symbol} Chart
      </div>
      <div className="relative">
        <svg width="100%" height="200" viewBox="0 0 100 100" preserveAspectRatio="none">
          {/* Grid lines */}
          <line x1="0" y1="20" x2="100" y2="20" stroke="#1a1f2e" strokeWidth="0.5" />
          <line x1="0" y1="50" x2="100" y2="50" stroke="#1a1f2e" strokeWidth="0.5" />
          <line x1="0" y1="80" x2="100" y2="80" stroke="#1a1f2e" strokeWidth="0.5" />
          
          {/* Price line */}
          <polyline
            points={points}
            fill="none"
            stroke="#00ff41"
            strokeWidth="2"
            vectorEffect="non-scaling-stroke"
          />
          
          {/* Current price dot */}
          <circle
            cx={100}
            cy={100 - ((data[data.length - 1].price - minPrice) / priceRange) * 80 + 10}
            r="2"
            fill="#00ff41"
          />
        </svg>
        
        <div className="flex justify-between text-xs mt-2" style={{ color: '#666' }}>
          <span>{data[0].time}</span>
          <span>Last: {data[data.length - 1].price.toFixed(2)}</span>
          <span>{data[data.length - 1].time}</span>
        </div>
      </div>
    </div>
  );
};