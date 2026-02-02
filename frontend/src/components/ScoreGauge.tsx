import React from 'react';

interface ScoreGaugeProps {
  score: number; // -1 to +1
  size?: 'sm' | 'md' | 'lg';
}

export const ScoreGauge: React.FC<ScoreGaugeProps> = ({ score, size = 'md' }) => {
  // Normalize score from -1 to 1 to a percentage (0-100)
  const percentage = ((score + 1) / 2) * 100;
  
  // Color based on score: red for negative, green for positive
  const getColor = () => {
    if (score < -0.5) return '#ff1f1f'; // Deep red
    if (score < 0) return '#ff7f7f'; // Light red
    if (score < 0.5) return '#ffff00'; // Yellow
    return '#00ff41'; // Green
  };
  
  const getSizeClasses = () => {
    switch (size) {
      case 'sm':
        return { container: 'w-16 h-16', text: 'text-xs' };
      case 'lg':
        return { container: 'w-32 h-32', text: 'text-lg' };
      default:
        return { container: 'w-24 h-24', text: 'text-sm' };
    }
  };

  const sizeClasses = getSizeClasses();
  const color = getColor();

  return (
    <div className={`${sizeClasses.container} relative flex items-center justify-center`}>
      {/* Outer circle border */}
      <svg
        className="absolute inset-0 w-full h-full"
        viewBox="0 0 100 100"
        style={{ transform: 'rotate(-90deg)' }}
      >
        {/* Background circle */}
        <circle
          cx="50"
          cy="50"
          r="40"
          fill="none"
          stroke="#1a1f2e"
          strokeWidth="2"
        />
        {/* Progress circle */}
        <circle
          cx="50"
          cy="50"
          r="40"
          fill="none"
          stroke={color}
          strokeWidth="3"
          strokeDasharray={`${(percentage / 100) * 251.2} 251.2`}
          style={{ transition: 'stroke-dasharray 0.3s ease' }}
        />
      </svg>

      {/* Center content */}
      <div className={`absolute text-center font-mono ${sizeClasses.text}`}>
        <div style={{ color }} className="font-bold">
          {score.toFixed(2)}
        </div>
        <div className="text-gray-400 text-[10px] uppercase tracking-widest">
          Score
        </div>
      </div>
    </div>
  );
};
