import React, { useState, useEffect, useRef } from 'react';

interface LogEntry {
  id: string;
  timestamp: string;
  message: string;
  type: 'info' | 'success' | 'warning' | 'error' | 'event';
}

interface ConsoleTabProps {
  logs?: LogEntry[];
  maxLogs?: number;
}

export const ConsoleTab: React.FC<ConsoleTabProps> = ({ 
  logs,
  maxLogs = 100 
}) => {
  const [displayedLogs, setDisplayedLogs] = useState<LogEntry[]>(logs || getDefaultLogs());
  const logsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [displayedLogs]);

  function getDefaultLogs(): LogEntry[] {
    return [
      {
        id: '1',
        timestamp: '13:10:45',
        message: '[POLYMARKET ALPHA SCANNER v2.1.0]',
        type: 'event',
      },
      {
        id: '2',
        timestamp: '13:10:45',
        message: 'Claude Code + Perplexity MCP Research Engine',
        type: 'info',
      },
      {
        id: '3',
        timestamp: '13:10:45',
        message: 'Initializing MCP connections...',
        type: 'info',
      },
      {
        id: '4',
        timestamp: '13:10:45',
        message: '✓ Connected: Polymarket REST API (ws://api.polymarket.com)',
        type: 'success',
      },
      {
        id: '5',
        timestamp: '13:10:45',
        message: '✓ Connected: Perplexity Research MCP (deep-research model)',
        type: 'success',
      },
      {
        id: '6',
        timestamp: '13:10:45',
        message: '✓ Connected: Claude Code Engine (Claude-opus-4-5)',
        type: 'success',
      },
      {
        id: '7',
        timestamp: '13:10:45',
        message: 'Fetching active markets from Polymarket...',
        type: 'info',
      },
      {
        id: '8',
        timestamp: '13:10:45',
        message: 'Found 847 active markets across 12 categories.',
        type: 'event',
      },
      {
        id: '9',
        timestamp: '13:10:45',
        message: 'Applying filters...',
        type: 'info',
      },
      {
        id: '10',
        timestamp: '13:10:45',
        message: '  — min_volume: $100,000  → 312 markets passed',
        type: 'info',
      },
      {
        id: '11',
        timestamp: '13:10:45',
        message: '  — min_liquidity: $50,000  → 189 markets passed',
        type: 'info',
      },
      {
        id: '12',
        timestamp: '13:10:45',
        message: 'Running alpha scoring algorithm on filtered markets...',
        type: 'event',
      },
      {
        id: '13',
        timestamp: '13:10:45',
        message: 'Completed probability edge | volume momentum | structural edge | time decay',
        type: 'success',
      },
      {
        id: '14',
        timestamp: '13:10:46',
        message: '[SIGNAL] TSLA unusual calls FSD by Mar 31? → Score: 0.78 (BUY)',
        type: 'event',
      },
      {
        id: '15',
        timestamp: '13:10:46',
        message: '[SIGNAL] Trump FSD 2024 prediction market → Score: 0.65 (BUY)',
        type: 'event',
      },
      {
        id: '16',
        timestamp: '13:10:46',
        message: '[SIGNAL] EUR/USD breakout setup → Score: 0.82 (SELL)',
        type: 'event',
      },
    ];
  }

  const getLogColor = (type: LogEntry['type']): string => {
    switch (type) {
      case 'success':
        return '#00ff41';
      case 'error':
        return '#ff1f1f';
      case 'warning':
        return '#ffff00';
      case 'event':
        return '#00ff41';
      case 'info':
      default:
        return '#aaa';
    }
  };

  return (
    <div
      className="flex-1 border rounded-sm font-mono text-xs overflow-hidden flex flex-col"
      style={{
        backgroundColor: '#0a0e27',
        borderColor: '#00ff41',
      }}
    >
      {/* Header */}
      <div
        className="px-4 py-2 border-b flex items-center justify-between"
        style={{ borderColor: '#00ff41' }}
      >
        <span
          className="uppercase tracking-widest font-bold text-xs"
          style={{ color: '#00ff41' }}
        >
          Console
        </span>
        <span style={{ color: '#666' }} className="text-[9px]">
          {displayedLogs.length} entries
        </span>
      </div>

      {/* Logs Container */}
      <div className="flex-1 overflow-y-auto p-4 space-y-1">
        {displayedLogs.map((log) => (
          <div key={log.id} className="font-mono text-xs">
            <span style={{ color: '#666' }}>[{log.timestamp}]</span>{' '}
            <span style={{ color: getLogColor(log.type) }}>
              {log.message}
            </span>
          </div>
        ))}
        <div ref={logsEndRef} />
      </div>

      {/* Bottom border accent */}
      <div
        className="h-px"
        style={{ backgroundColor: '#00ff41', opacity: 0.3 }}
      />
    </div>
  );
};
