import React, { useState, useEffect } from 'react';

interface SidebarProps {
  balance?: number;
  activePositions?: number;
  activeSignals?: number;
  equity?: number;
  marginUsed?: number;
  winRate?: number;
  lastScan?: string;
}

export const Sidebar: React.FC<SidebarProps> = ({
  balance: propBalance,
  activePositions: propActivePositions,
  activeSignals: propActiveSignals,
  equity: propEquity,
  marginUsed: propMarginUsed,
  winRate: propWinRate,
  lastScan: propLastScan,
}) => {
  const [balance, setBalance] = useState(propBalance || 1000);
  const [equity, setEquity] = useState(propEquity || 1000);
  const [activePositions, setActivePositions] = useState(propActivePositions || 0);
  const [lastScan, setLastScan] = useState(propLastScan || "Just now");
  const [isScanning, setIsScanning] = useState(false);
  const marginUsed = propMarginUsed || 0;
  const winRate = propWinRate || 0;
  const activeSignals = propActiveSignals || 0;

  useEffect(() => {
    // Fetch account data and check scanning status from backend
    const fetchData = async () => {
      try {
        // Fetch account
        const accResponse = await fetch('/api/account');
        if (accResponse.ok) {
          const data = await accResponse.json();
          setBalance(data.balance || 1000);
          setEquity(data.equity || 1000);
          setActivePositions(data.positions || 0);
          if (data.last_scan) {
            const scanTime = new Date(data.last_scan);
            const now = new Date();
            const diffSecs = Math.floor((now.getTime() - scanTime.getTime()) / 1000);
            if (diffSecs < 10) {
              setLastScan("Now");
            } else if (diffSecs < 60) {
              setLastScan(`${diffSecs}s ago`);
            } else if (diffSecs < 3600) {
              const mins = Math.floor(diffSecs / 60);
              setLastScan(`${mins}m ${diffSecs % 60}s ago`);
            } else {
              const hours = Math.floor(diffSecs / 3600);
              const mins = Math.floor((diffSecs % 3600) / 60);
              setLastScan(`${hours}h ${mins}m ago`);
            }
          }
        }

        // Fetch logs to check if scanning
        const logsResponse = await fetch('/api/logs');
        if (logsResponse.ok) {
          const logsData = await logsResponse.json();
          if (logsData.logs && logsData.logs.length > 0) {
            const recentLogs = logsData.logs.slice(-10);
            const scanning = recentLogs.some((log: any) =>
              log.message.includes('Fetching data') ||
              log.message.includes('Fetching news') ||
              log.message.includes('Generating signals')
            );
            setIsScanning(scanning);
          }
        }
      } catch (error) {
        console.error('Failed to fetch data:', error);
      }
    };

    fetchData();
    // Update more frequently to show accurate time difference
    const interval = setInterval(fetchData, 1000); // Poll every second
    return () => clearInterval(interval);
  }, []);
  const statItems = [
    { label: 'Balance', value: `$${balance.toLocaleString()}`, highlight: true },
    { label: 'Equity', value: `$${equity.toLocaleString()}` },
    { label: 'Active Positions', value: activePositions.toString(), highlight: true },
    { label: 'Active Signals', value: activeSignals.toString(), highlight: true },
    { label: 'Margin Used', value: `${marginUsed}%` },
    { label: 'Win Rate', value: `${winRate}%` },
  ];

  return (
    <div
      className="w-56 border-r"
      style={{
        backgroundColor: '#0a0e27',
        borderColor: '#00ff41',
      }}
    >
      {/* Header */}
      <div className="p-4 border-b" style={{ borderColor: '#00ff41' }}>
        <h2
          className="font-mono text-xs uppercase tracking-widest font-bold"
          style={{ color: '#00ff41' }}
        >
          Account Stats
        </h2>
      </div>

      {/* Stats List */}
      <div className="p-4 space-y-4">
        {statItems.map((item, idx) => (
          <div key={idx} className="border-b pb-3" style={{ borderColor: '#1a1f2e' }}>
            <div
              className="font-mono text-[10px] uppercase tracking-widest mb-1"
              style={{ color: '#888' }}
            >
              {item.label}
            </div>
            <div
              className={`font-mono font-bold text-sm ${
                item.highlight ? 'text-lg' : ''
              }`}
              style={{ color: item.highlight ? '#00ff41' : '#aaa' }}
            >
              {item.value}
            </div>
          </div>
        ))}
      </div>

      {/* Scanner Info Section */}
      <div className="p-4 mt-4 border-t" style={{ borderColor: '#1a1f2e' }}>
        <h3
          className="font-mono text-xs uppercase tracking-widest font-bold mb-3"
          style={{ color: '#00ff41' }}
        >
          Scan Config
        </h3>
        <div className="space-y-2 text-[10px] font-mono">
          <div className="flex justify-between">
            <span style={{ color: '#888' }}>Min Volume</span>
            <span style={{ color: '#00ff41' }}>$100K</span>
          </div>
          <div className="flex justify-between">
            <span style={{ color: '#888' }}>Volatility</span>
            <span style={{ color: '#00ff41' }}>5-20%</span>
          </div>
          <div className="flex justify-between">
            <span style={{ color: '#888' }}>Lookback</span>
            <span style={{ color: '#00ff41' }}>4h</span>
          </div>
          <div className="flex justify-between">
            <span style={{ color: '#888' }}>Score Min</span>
            <span style={{ color: '#00ff41' }}>0.50</span>
          </div>
        </div>
      </div>

      {/* Status Indicator */}
      <div className="p-4 mt-4 border-t border-l-4" 
        style={{ 
          borderTopColor: '#1a1f2e',
          borderLeftColor: '#00ff41',
          backgroundColor: 'rgba(0, 255, 65, 0.05)'
        }}>
        <div className="flex items-center gap-2 mb-1">
          <div 
            className={`w-2 h-2 rounded-full ${isScanning ? 'animate-pulse' : ''}`}
            style={{ backgroundColor: isScanning ? '#00ff41' : '#666' }}
          />
          <span 
            className="font-mono text-xs" 
            style={{ color: isScanning ? '#00ff41' : '#666' }}
          >
            {isScanning ? 'SCANNING' : 'IDLE'}
          </span>
        </div>
        <div className="font-mono text-[9px]" style={{ color: '#666' }}>
          Last scan: {lastScan}
        </div>
      </div>
    </div>
  );
};
