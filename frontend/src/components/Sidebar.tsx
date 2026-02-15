import React, { useState, useEffect } from 'react';
import { apiUrl } from '../api';

interface SidebarProps {
  accountData?: any;
}

export const Sidebar: React.FC<SidebarProps> = ({ accountData }) => {
  const [lastScan, setLastScan] = useState("--");
  const [isScanning, setIsScanning] = useState(false);

  const balance = accountData?.balance_pln ?? 10000;
  const equity = accountData?.equity_pln ?? 10000;
  const balanceUsd = accountData?.balance_usd ?? 2469.14;
  const openTrades = accountData?.open_trades ?? 0;
  const closedTrades = accountData?.closed_trades ?? 0;
  const winRate = accountData?.win_rate ?? 0;
  const totalPnl = accountData?.total_pnl_pln ?? 0;
  const mode = accountData?.mode ?? 'simulate';

  useEffect(() => {
    const updateScan = () => {
      if (accountData?.last_scan) {
        const scanTime = new Date(accountData.last_scan);
        const now = new Date();
        const diffSecs = Math.floor((now.getTime() - scanTime.getTime()) / 1000);
        if (diffSecs < 5) setLastScan("Now");
        else if (diffSecs < 60) setLastScan(`${diffSecs}s ago`);
        else if (diffSecs < 3600) setLastScan(`${Math.floor(diffSecs / 60)}m ago`);
        else setLastScan(`${Math.floor(diffSecs / 3600)}h ago`);
      }
    };
    updateScan();
    const interval = setInterval(updateScan, 1000);
    return () => clearInterval(interval);
  }, [accountData]);

  const toggleMode = async () => {
    const newMode = mode === 'simulate' ? 'live' : 'simulate';
    try {
      await fetch(`${apiUrl('account/mode')}?mode=${newMode}`, { method: 'POST' });
    } catch (error) {
      console.error('Failed to toggle mode:', error);
    }
  };

  const resetAccount = async () => {
    try {
      await fetch(apiUrl('account/reset'), { method: 'POST' });
    } catch (error) {
      console.error('Failed to reset account:', error);
    }
  };

  const pnlColor = totalPnl >= 0 ? '#22c55e' : '#ef4444';
  const equityChange = equity - 10000;
  const equityChangePct = ((equity - 10000) / 10000 * 100);

  return (
    <div
      className="w-60 h-full flex flex-col overflow-y-auto"
      style={{ backgroundColor: '#0d1220', borderRight: '1px solid #1a1f35' }}
    >
      {/* Balance Section */}
      <div className="p-4" style={{ borderBottom: '1px solid #1a1f35' }}>
        <div className="text-[10px] uppercase tracking-widest mb-1.5" style={{ color: '#4a5568' }}>
          Balance
        </div>
        <div className="text-lg font-bold mb-0.5" style={{ color: '#e2e8f0' }}>
          {balance.toLocaleString('pl-PL', { minimumFractionDigits: 2 })} <span className="text-xs font-normal" style={{ color: '#64748b' }}>PLN</span>
        </div>
        <div className="text-[11px]" style={{ color: '#64748b' }}>
          ${balanceUsd.toLocaleString('en-US', { minimumFractionDigits: 2 })} USD
        </div>
      </div>

      {/* Equity Section */}
      <div className="p-4" style={{ borderBottom: '1px solid #1a1f35' }}>
        <div className="text-[10px] uppercase tracking-widest mb-1.5" style={{ color: '#4a5568' }}>
          Equity
        </div>
        <div className="text-base font-bold" style={{ color: '#e2e8f0' }}>
          {equity.toLocaleString('pl-PL', { minimumFractionDigits: 2 })} <span className="text-[10px] font-normal" style={{ color: '#64748b' }}>PLN</span>
        </div>
        <div className="flex items-center gap-1.5 mt-1">
          <span className="text-[11px] font-medium" style={{ color: pnlColor }}>
            {equityChange >= 0 ? '+' : ''}{equityChange.toFixed(2)} PLN
          </span>
          <span className="text-[10px]" style={{ color: pnlColor }}>
            ({equityChangePct >= 0 ? '+' : ''}{equityChangePct.toFixed(2)}%)
          </span>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="p-4 grid grid-cols-2 gap-3" style={{ borderBottom: '1px solid #1a1f35' }}>
        <StatBox label="Open" value={openTrades.toString()} color="#3b82f6" />
        <StatBox label="Closed" value={closedTrades.toString()} color="#64748b" />
        <StatBox label="Win Rate" value={`${winRate}%`} color={winRate >= 50 ? '#22c55e' : winRate > 0 ? '#ef4444' : '#64748b'} />
        <StatBox label="Total P&L" value={`${totalPnl >= 0 ? '+' : ''}${totalPnl.toFixed(0)}`} color={pnlColor} />
      </div>

      {/* Mode Toggle */}
      <div className="p-4" style={{ borderBottom: '1px solid #1a1f35' }}>
        <div className="text-[10px] uppercase tracking-widest mb-2" style={{ color: '#4a5568' }}>
          Trading Mode
        </div>
        <button
          onClick={toggleMode}
          className="w-full text-[11px] font-bold py-2 rounded-sm border transition-all"
          style={{
            backgroundColor: mode === 'simulate' ? 'rgba(234, 179, 8, 0.08)' : 'rgba(239, 68, 68, 0.08)',
            borderColor: mode === 'simulate' ? 'rgba(234, 179, 8, 0.3)' : 'rgba(239, 68, 68, 0.3)',
            color: mode === 'simulate' ? '#eab308' : '#ef4444',
          }}
        >
          {mode === 'simulate' ? 'SIMULATION MODE' : 'LIVE MODE'}
        </button>
        <div className="text-[9px] mt-1.5 text-center" style={{ color: '#374151' }}>
          {mode === 'simulate' ? 'Paper trading with virtual PLN' : 'Real trading - use caution'}
        </div>
      </div>

      {/* Instruments */}
      <div className="p-4" style={{ borderBottom: '1px solid #1a1f35' }}>
        <div className="text-[10px] uppercase tracking-widest mb-2.5" style={{ color: '#4a5568' }}>
          Instruments
        </div>
        <div className="space-y-1.5">
          {[
            { symbol: 'XAU', name: 'Gold', color: '#eab308' },
            { symbol: 'XAG', name: 'Silver', color: '#94a3b8' },
            { symbol: 'US100', name: 'Nasdaq', color: '#3b82f6' },
            { symbol: 'BTC', name: 'Bitcoin', color: '#f97316' },
          ].map((inst) => (
            <div key={inst.symbol} className="flex items-center justify-between py-1">
              <div className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: inst.color }} />
                <span className="text-[11px] font-medium" style={{ color: '#c8cdd8' }}>
                  {inst.symbol}
                </span>
              </div>
              <span className="text-[10px]" style={{ color: '#4a5568' }}>
                {inst.name}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Scanner Status */}
      <div className="p-4" style={{ borderBottom: '1px solid #1a1f35' }}>
        <div className="flex items-center justify-between mb-2">
          <div className="text-[10px] uppercase tracking-widest" style={{ color: '#4a5568' }}>
            Scanner
          </div>
          <div className="flex items-center gap-1.5">
            <div
              className={`w-1.5 h-1.5 rounded-full ${isScanning ? 'animate-pulse' : ''}`}
              style={{ backgroundColor: '#22c55e' }}
            />
            <span className="text-[10px]" style={{ color: '#22c55e' }}>
              Active
            </span>
          </div>
        </div>
        <div className="text-[10px]" style={{ color: '#374151' }}>
          Last scan: {lastScan}
        </div>
      </div>

      {/* Reset Button */}
      <div className="p-4 mt-auto">
        <button
          onClick={resetAccount}
          className="w-full text-[10px] py-1.5 rounded-sm border transition-all hover:bg-opacity-10"
          style={{
            borderColor: '#1a1f35',
            color: '#4a5568',
          }}
        >
          Reset Account
        </button>
      </div>
    </div>
  );
};

const StatBox: React.FC<{ label: string; value: string; color: string }> = ({ label, value, color }) => (
  <div
    className="p-2.5 rounded-sm"
    style={{ backgroundColor: '#0b0f1a' }}
  >
    <div className="text-[9px] uppercase tracking-widest mb-1" style={{ color: '#4a5568' }}>
      {label}
    </div>
    <div className="text-sm font-bold" style={{ color }}>
      {value}
    </div>
  </div>
);
