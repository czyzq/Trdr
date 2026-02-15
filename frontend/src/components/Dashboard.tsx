import React, { useState, useEffect } from 'react';
import { Sidebar } from './Sidebar';
import { SignalsGrid } from './SignalsGrid';
import { ConsoleTab } from './ConsoleTab';
import { NewsTab } from './NewsTab';
import { ChartsTab } from './ChartsTab';
import { MainTab } from './MainTab';
import { TradesTab } from './TradesTab';
import { apiUrl } from '../api';

type TabType = 'main' | 'charts' | 'trades' | 'news' | 'console' | 'settings';

interface LogEntry {
  id: string;
  timestamp: string;
  message: string;
  type: 'info' | 'success' | 'warning' | 'error' | 'event';
}

export const Dashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>(() => {
    const saved = localStorage.getItem('cfd_activeTab');
    return (saved as TabType) || 'main';
  });
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [currentTime, setCurrentTime] = useState<string>(new Date().toLocaleTimeString('en-GB'));
  const [selectedSymbol, setSelectedSymbol] = useState<string>(() => {
    return localStorage.getItem('cfd_selectedSymbol') || 'XAU';
  });
  const [accountData, setAccountData] = useState<any>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => { localStorage.setItem('cfd_activeTab', activeTab); }, [activeTab]);
  useEffect(() => { localStorage.setItem('cfd_selectedSymbol', selectedSymbol); }, [selectedSymbol]);

  useEffect(() => {
    const timeInterval = setInterval(() => {
      setCurrentTime(new Date().toLocaleTimeString('en-GB'));
    }, 1000);

    const fetchData = async () => {
      try {
        const [logsRes, accRes] = await Promise.all([
          fetch(apiUrl('logs')),
          fetch(apiUrl('account'))
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

  // Close sidebar when switching tabs on mobile
  const handleTabSwitch = (tab: TabType) => {
    setActiveTab(tab);
    setSidebarOpen(false);
  };

  const tabs: Array<{ id: TabType; label: string; shortLabel: string; icon: string }> = [
    { id: 'main', label: 'Dashboard', shortLabel: 'Home', icon: '◎' },
    { id: 'charts', label: 'Charts', shortLabel: 'Charts', icon: '◩' },
    { id: 'trades', label: 'Trades', shortLabel: 'Trades', icon: '⇅' },
    { id: 'news', label: 'News', shortLabel: 'News', icon: '◉' },
    { id: 'console', label: 'Console', shortLabel: 'Log', icon: '▸' },
    { id: 'settings', label: 'Settings', shortLabel: 'Set.', icon: '⚙' },
  ];

  return (
    <div className="w-full h-screen flex flex-col" style={{ backgroundColor: '#0b0f1a' }}>
      {/* Top Header Bar */}
      <div
        className="flex items-center justify-between px-3 md:px-5 py-2 md:py-2.5 flex-shrink-0"
        style={{ backgroundColor: '#0d1220', borderBottom: '1px solid #1a1f35' }}
      >
        <div className="flex items-center gap-2 md:gap-4">
          {/* Mobile sidebar toggle */}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="md:hidden flex items-center justify-center w-7 h-7 rounded-sm"
            style={{ backgroundColor: sidebarOpen ? '#1a1f35' : 'transparent', color: '#64748b' }}
          >
            <span className="text-sm">{sidebarOpen ? '✕' : '☰'}</span>
          </button>

          <div className="flex items-center gap-2">
            <div
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: '#22c55e' }}
            />
            <span
              className="text-xs font-bold tracking-wider uppercase hidden sm:inline"
              style={{ color: '#e2e8f0', letterSpacing: '0.15em' }}
            >
              CFD Trading Bot
            </span>
            <span
              className="text-xs font-bold tracking-wider uppercase sm:hidden"
              style={{ color: '#e2e8f0', letterSpacing: '0.15em' }}
            >
              CFD Bot
            </span>
          </div>
          <span
            className="text-[10px] px-2 py-0.5 rounded-sm font-medium hidden sm:inline-block"
            style={{ backgroundColor: '#1a1f35', color: '#64748b' }}
          >
            v0.2.0
          </span>
          <span
            className="text-[10px] px-1.5 py-0.5 rounded-sm font-medium"
            style={{
              backgroundColor: accountData?.mode === 'simulate' ? 'rgba(234, 179, 8, 0.15)' : 'rgba(239, 68, 68, 0.15)',
              color: accountData?.mode === 'simulate' ? '#eab308' : '#ef4444',
            }}
          >
            {accountData?.mode === 'simulate' ? 'SIM' : 'LIVE'}
          </span>
        </div>

        {/* Desktop Tab Navigation */}
        <div className="hidden md:flex items-center gap-1">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => handleTabSwitch(tab.id)}
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
          <span className="text-[11px] font-medium hidden sm:inline" style={{ color: '#4a5568' }}>
            {currentTime}
          </span>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex flex-1 overflow-hidden relative">
        {/* Mobile sidebar overlay */}
        {sidebarOpen && (
          <div
            className="md:hidden fixed inset-0 z-40"
            style={{ backgroundColor: 'rgba(0,0,0,0.6)', top: '44px' }}
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* Sidebar - hidden on mobile, slides in when toggled */}
        <div className={`
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
          md:translate-x-0 md:relative
          fixed top-[44px] left-0 bottom-[52px] md:bottom-0
          z-50 transition-transform duration-200 ease-in-out
        `}>
          <Sidebar accountData={accountData} />
        </div>

        {/* Tab Content */}
        <div className="flex-1 overflow-hidden flex flex-col min-h-0">
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
            <div className="flex-1 min-h-0 h-full">
              <ConsoleTab logs={logs && logs.length > 0 ? logs : undefined} maxLogs={100} />
            </div>
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

      {/* Mobile Bottom Navigation */}
      <div
        className="md:hidden flex items-center justify-around flex-shrink-0"
        style={{
          backgroundColor: '#0d1220',
          borderTop: '1px solid #1a1f35',
          paddingBottom: 'env(safe-area-inset-bottom, 0px)',
        }}
      >
        {tabs.slice(0, 5).map((tab) => (
          <button
            key={tab.id}
            onClick={() => handleTabSwitch(tab.id)}
            className="flex flex-col items-center py-2 px-2 min-w-[52px] transition-all"
            style={{
              color: activeTab === tab.id ? '#e2e8f0' : '#4a5568',
            }}
          >
            <span className="text-base leading-none mb-0.5">{tab.icon}</span>
            <span className="text-[9px] font-medium">{tab.shortLabel}</span>
          </button>
        ))}
      </div>

      {/* Desktop Footer */}
      <div
        className="hidden md:flex items-center justify-between px-5 py-1.5 text-[10px] flex-shrink-0"
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
