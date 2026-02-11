import React, { useState, useEffect } from 'react';
import { Sidebar } from './Sidebar';
import { SignalsGrid } from './SignalsGrid';
import { ConsoleTab } from './ConsoleTab';
import { NewsTab } from './NewsTab';
import { ChartsTab } from './ChartsTab';
import { MainTab } from './MainTab';
import { TradesTab } from './TradesTab';

type TabType = 'main' | 'charts' | 'trades' | 'news' | 'console' | 'settings';

interface LogEntry {
  id: string;
  timestamp: string;
  message: string;
  type: 'info' | 'success' | 'warning' | 'error' | 'event';
}

export const Dashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>('main');
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [currentTime, setCurrentTime] = useState<string>(new Date().toLocaleTimeString('en-GB'));
  const [selectedSymbol, setSelectedSymbol] = useState<string>('XAU');
  const [accountData, setAccountData] = useState<any>(null);

  useEffect(() => {
    const timeInterval = setInterval(() => {
      setCurrentTime(new Date().toLocaleTimeString('en-GB'));
    }, 1000);

    const fetchData = async () => {
      try {
        const [logsRes, accRes] = await Promise.all([
          fetch('/api/logs'),
          fetch('/api/account')
        ]);
        if (logsRes.ok) {
          const data = await logsRes.json();
          if (data.logs) setLogs(data.logs);
        }
        if (accRes.ok) {
          const data = await accRes.json();
          setAccountData(data);
        }
      } catch (error) {
        console.error('Failed to fetch data:', error);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 3000);

    return () => {
      clearInterval(timeInterval);
      clearInterval(interval);
    };
  }, []);

  const tabs: Array<{ id: TabType; label: string; icon: string }> = [
    { id: 'main', label: 'Dashboard', icon: 'D' },
    { id: 'charts', label: 'Charts', icon: 'C' },
    { id: 'trades', label: 'Trades', icon: 'T' },
    { id: 'news', label: 'News', icon: 'N' },
    { id: 'console', label: 'Console', icon: '>' },
    { id: 'settings', label: 'Settings', icon: 'S' },
  ];

  return (
    <div className="w-full h-screen flex flex-col" style={{ backgroundColor: '#0b0f1a' }}>
      {/* Top Header Bar */}
      <div
        className="flex items-center justify-between px-5 py-2.5"
        style={{ backgroundColor: '#0d1220', borderBottom: '1px solid #1a1f35' }}
      >
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: '#22c55e' }}
            />
            <span
              className="text-xs font-bold tracking-wider uppercase"
              style={{ color: '#e2e8f0', letterSpacing: '0.15em' }}
            >
              CFD Trading Bot
            </span>
          </div>
          <span
            className="text-[10px] px-2 py-0.5 rounded-sm font-medium"
            style={{ backgroundColor: '#1a1f35', color: '#64748b' }}
          >
            v0.2.0
          </span>
          <span
            className="text-[10px] px-2 py-0.5 rounded-sm font-medium"
            style={{
              backgroundColor: accountData?.mode === 'simulate' ? 'rgba(234, 179, 8, 0.15)' : 'rgba(239, 68, 68, 0.15)',
              color: accountData?.mode === 'simulate' ? '#eab308' : '#ef4444',
            }}
          >
            {accountData?.mode === 'simulate' ? 'SIMULATION' : 'LIVE'}
          </span>
        </div>

        {/* Tab Navigation in Header */}
        <div className="flex items-center gap-1">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className="px-3 py-1.5 text-[11px] font-medium tracking-wide uppercase transition-all rounded-sm"
              style={{
                color: activeTab === tab.id ? '#e2e8f0' : '#4a5568',
                backgroundColor: activeTab === tab.id ? '#1a1f35' : 'transparent',
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-4">
          <span className="text-[11px] font-medium" style={{ color: '#4a5568' }}>
            {currentTime}
          </span>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <Sidebar accountData={accountData} />

        {/* Tab Content */}
        <div className="flex-1 overflow-hidden">
          {activeTab === 'main' && (
            <MainTab
              onSignalClick={(signal) => console.log('Signal clicked:', signal)}
              selectedSymbol={selectedSymbol}
              onSymbolSelect={setSelectedSymbol}
            />
          )}
          {activeTab === 'charts' && <ChartsTab />}
          {activeTab === 'trades' && <TradesTab />}
          {activeTab === 'news' && <NewsTab />}
          {activeTab === 'console' && (
            <ConsoleTab logs={logs && logs.length > 0 ? logs : undefined} maxLogs={100} />
          )}
          {activeTab === 'settings' && (
            <div className="h-full flex items-center justify-center" style={{ color: '#4a5568' }}>
              <div className="text-center">
                <div className="text-xs uppercase tracking-widest mb-2" style={{ color: '#64748b' }}>
                  Settings
                </div>
                <div className="text-xs">Configuration panel coming soon</div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Footer */}
      <div
        className="flex items-center justify-between px-5 py-1.5 text-[10px]"
        style={{ backgroundColor: '#0d1220', borderTop: '1px solid #1a1f35', color: '#374151' }}
      >
        <span>CFD Trading Bot | XAU, XAG, US100, BTC</span>
        <div className="flex items-center gap-3">
          <span>PLN/USD: 4.05</span>
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: '#22c55e' }} />
            Connected
          </span>
        </div>
      </div>
    </div>
  );
};
