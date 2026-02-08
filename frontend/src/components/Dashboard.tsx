import React, { useState, useEffect } from 'react';
import { Sidebar } from './Sidebar';
import { SignalsGrid } from './SignalsGrid';
import { ConsoleTab } from './ConsoleTab';
import { NewsTab } from './NewsTab';
import { ChartsTab } from './ChartsTab';
import { MainTab } from './MainTab';
import { ChartTest } from './ChartTest';

type TabType = 'main' | 'signals' | 'news' | 'charts' | 'history' | 'console' | 'settings' | 'test';

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
  const [activeTab, setActiveTab] = useState<TabType>('main');
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [currentTime, setCurrentTime] = useState<string>(new Date().toLocaleTimeString('en-GB'));
  const [selectedSymbol, setSelectedSymbol] = useState<string>('XAU');
  const [accountData, setAccountData] = useState<any>(null);

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
          }
        }
      } catch (error) {
        console.error('Failed to fetch logs:', error);
      }
    };

    // Fetch account data
    const fetchAccount = async () => {
      try {
        const response = await fetch('/api/account');
        if (response.ok) {
          const data = await response.json();
          setAccountData(data);
        }
      } catch (error) {
        console.error('Failed to fetch account data:', error);
      }
    };

    fetchLogs();
    fetchAccount();

    // Poll for data every 5 seconds
    const interval = setInterval(() => {
      fetchLogs();
      fetchAccount();
    }, 5000);
    
    return () => {
      clearInterval(timeInterval);
      clearInterval(interval);
    };
  }, []);

  const tabs: Array<{ id: TabType; label: string }> = [
    { id: 'main', label: 'MAIN' },
    { id: 'charts', label: 'Charts' },
    { id: 'news', label: 'News' },
    { id: 'history', label: 'History' },
    { id: 'console', label: 'Console' },
    { id: 'settings', label: 'Settings' },
    { id: 'test', label: 'Test' },
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
            <span>{currentTime}</span>
          </div>
        </div>
      </div>

      {/* Main Container */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <Sidebar
          balance={accountData?.balance}
          activePositions={accountData?.positions}
          activeSignals={3} // This will be updated by signals data
          equity={accountData?.equity}
          marginUsed={accountData ? ((accountData.balance - accountData.available) / accountData.balance * 100) : 0}
          winRate={62.5} // This could be calculated from trade history
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
            {activeTab === 'main' && (
              <MainTab
                onSignalClick={(signal) => {
                  console.log('Signal clicked:', signal);
                }}
                selectedSymbol={selectedSymbol}
                onSymbolSelect={setSelectedSymbol}
              />
            )}

            {activeTab === 'news' && <NewsTab />}

            {activeTab === 'charts' && <ChartsTab />}

            {activeTab === 'test' && <ChartTest symbol={selectedSymbol} />}

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
