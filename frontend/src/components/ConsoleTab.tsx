import React, { useState, useEffect, useRef } from "react";

interface LogEntry {
  id: string;
  timestamp: string;
  message: string;
  type: "info" | "success" | "warning" | "error" | "event";
}

interface ConsoleTabProps {
  logs?: LogEntry[];
  maxLogs?: number;
}

export const ConsoleTab: React.FC<ConsoleTabProps> = ({
  logs,
  maxLogs = 100,
}) => {
  const [displayedLogs, setDisplayedLogs] = useState<LogEntry[]>(logs || []);
  const logsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [displayedLogs]);

  const getLogColor = (type: LogEntry["type"]): string => {
    switch (type) {
      case "success":
        return "#00ff41";
      case "error":
        return "#ff1f1f";
      case "warning":
        return "#ffff00";
      case "event":
        return "#00ff41";
      case "info":
      default:
        return "#aaa";
    }
  };

  return (
    <div
      className="h-full border rounded-sm font-mono text-xs flex flex-col"
      style={{
        backgroundColor: "var(--bg-secondary)",
        borderColor: "var(--border)",
        minHeight: "0",
      }}
    >
      {/* Header */}
      <div
        className="px-4 py-2 border-b flex items-center justify-between flex-shrink-0"
        style={{ borderColor: "var(--border)" }}
      >
        <span
          className="uppercase tracking-widest font-bold text-xs"
          style={{ color: "var(--accent)" }}
        >
          Console
        </span>
        <span style={{ color: "var(--text-muted)" }} className="text-[9px]">
          {displayedLogs.length} entries
        </span>
      </div>

      {/* Logs Container - scrollable */}
      <div
        className="flex-1 overflow-y-auto p-4 space-y-1"
        style={{
          minHeight: "0",
          maxHeight: "calc(100vh - 200px)",
        }}
      >
        {displayedLogs.map((log, index) => (
          <div key={`${log.id}-${index}`} className="font-mono text-xs">
            <span style={{ color: "var(--text-muted)" }}>[{log.timestamp}]</span>{" "}
            <span style={{ color: getLogColor(log.type) }}>{log.message}</span>
          </div>
        ))}
        <div ref={logsEndRef} />
      </div>

      {/* Bottom border accent */}
      <div
        className="h-px"
        style={{ backgroundColor: "var(--accent)", opacity: 0.3 }}
      />
    </div>
  );
};
