import React, { useState, useEffect } from 'react';
import { Sidebar } from './Sidebar';
import { SignalsGrid } from './SignalsGrid';
import { ConsoleTab } from './ConsoleTab';

type TabType = 'signals' | 'history' | 'console' | 'settings';

interface LogEntry {
  id: string;
  timestamp: string;
  message: string;
  type: 'info' | 'success' | 'warning' | 'error' | 'event';
}

interface DashboardProps {
  title?: string;
  version?: string;
}

export const Dashboard: React.FC<DashboardProps> = ({
  title = 'CFD Trading Bot',
  version = 'v0.1.0',
}) => {
  const [activeTab, setActiveTab] = useState<TabType>('signals');
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [currentTime, setCurrentTime] = useState<string>(new Date().toLocaleTimeString('en-GB'));
  const [isScanning, setIsScanning] = useState(false);

  useEffect(() => {
    // Update current time every second
    const timeInterval = setInterval(() => {
      setCurrentTime(new Date().toLocaleTimeString('en-GB'));
    }, 1000);

    // Fetch logs from backend
    const fetchLogs = async () => {
      try {
        const response = await fetch('/api/logs');
        if (response.ok) {
          const data = await response.json();
          if (data.logs) {
            setLogs(data.logs);
            // Check if currently scanning
            const recentLogs = data.logs.slice(-5);
            const scanning = recentLogs.some((log: LogEntry) => 
              log.message.includes('Fetching data') || 
              log.message.includes('Generating signals')
            );
            setIsScanning(scanning);
          }
        }
      } catch (error) {
        console.error('Failed to fetch logs:', error);
      }
    };

    fetchLogs();

    // Poll for logs every 5 seconds
    const logInterval = setInterval(fetchLogs, 5000);
    
    return () => {
      clearInterval(timeInterval);
      clearInterval(logInterval);
    };
  }, []);

  const tabs: Array<{ id: TabType; label: string }> = [
    { id: 'signals', label: 'Signals' },
    { id: 'history', label: 'History' },
    { id: 'console', label: 'Console' },
    { id: 'settings', label: 'Settings' },
  ];

  return (
    <div
      className="w-full h-screen flex flex-col font-mono"
      style={{ backgroundColor: '#0a0e27' }}
    >
      {/* Top Header */}
      <div
        className="border-b px-6 py-4"
        style={{ borderColor: '#00ff41' }}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1
              className="text-sm font-bold uppercase tracking-widest"
              style={{ color: '#00ff41' }}
            >
              {title}
            </h1>
            <span
              className="text-xs px-2 py-1 rounded"
              style={{
                color: '#00ff41',
                borderColor: '#00ff41',
                border: '1px solid',
              }}
            >
              {version}
            </span>
          </div>
          <div className="flex items-center gap-4 text-xs" style={{ color: '#666' }}>
            <div className="flex items-center gap-2">
              <div
                className={`w-2 h-2 rounded-full ${isScanning ? 'animate-pulse' : ''}`}
                style={{ backgroundColor: isScanning ? '#ff6b6b' : '#00ff41' }}
              />
              <span>{isScanning ? 'SCANNING' : 'LIVE'}</span>
            </div>
            <span>{currentTime}</span>
          </div>
        </div>
      </div>

      {/* Main Container */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <Sidebar
          balance={25000}
          activePositions={3}
          activeSignals={12}
          equity={25300}
          marginUsed={45}
          winRate={62.5}
        />

        {/* Main Content */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Tab Navigation */}
          <div
            className="border-b px-6 py-4 flex gap-8"
            style={{ borderColor: '#1a1f2e' }}
          >
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`font-mono text-xs uppercase tracking-widest font-bold pb-2 transition border-b-2 ${
                  activeTab === tab.id ? 'border-opacity-100' : 'border-opacity-0'
                }`}
                style={{
                  color: activeTab === tab.id ? '#00ff41' : '#666',
                  borderColor: '#00ff41',
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Tab Content */}
          <div className="flex-1 overflow-hidden p-4">
            {activeTab === 'signals' && (
              <SignalsGrid
                signals={undefined}
                onSignalClick={(signal) => {
                  console.log('Signal clicked:', signal);
                }}
              />
            )}

            {activeTab === 'console' && (
              <ConsoleTab logs={logs && logs.length > 0 ? logs : undefined} maxLogs={100} />
            )}

            {activeTab === 'history' && (
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
                    Trade History
                  </div>
                  <div style={{ color: '#666' }} className="text-xs">
                    Historical data and closed trades coming soon...
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'settings' && (
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
                    Settings
                  </div>
                  <div style={{ color: '#666' }} className="text-xs">
                    Configuration panel coming soon...
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Footer */}
      <div
        className="border-t px-6 py-2 text-xs"
        style={{
          borderColor: '#1a1f2e',
          color: '#666',
        }}
      >
        <div className="flex items-center justify-between">
          <span>Claude Code + Perplexity MCP | Realtime Market Analysis</span>
          <span>Connected to Live Data Streams</span>
        </div>
      </div>
    </div>
  );
};
