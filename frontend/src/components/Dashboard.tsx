import React, { useState, useEffect } from "react";
import { Sidebar } from "./Sidebar";
import { SignalsGrid } from "./SignalsGrid";
import { ConsoleTab } from "./ConsoleTab";
import { NewsTab } from "./NewsTab";
import { ChartsTab } from "./ChartsTab";
import { MainTab } from "./MainTab";
import { TradesTab } from "./TradesTab";
import { SettingsTab } from "./SettingsTab";
import { apiUrl } from "../api";
import { getStoredTheme, themes, ThemeName } from "../theme";

type TabType = "main" | "charts" | "trades" | "news" | "console" | "settings" | "backtest";

interface LogEntry {
  id: string;
  timestamp: string;
  message: string;
  type: "info" | "success" | "warning" | "error" | "event";
}

export const Dashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>(() => {
    const saved = localStorage.getItem("cfd_activeTab");
    return (saved as TabType) || "main";
  });
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [currentTime, setCurrentTime] = useState<string>(
    new Date().toLocaleTimeString("en-GB", { timeZone: "Europe/Warsaw" }),
  );
  const [selectedSymbol, setSelectedSymbol] = useState<string>(() => {
    return localStorage.getItem("cfd_selectedSymbol") || "XAU";
  });
  const [accountData, setAccountData] = useState<any>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [theme, setTheme] = useState<ThemeName>(getStoredTheme());
  const [broker, setBroker] = useState<"simulation" | "ibkr">("simulation");
  const [autoTrade, setAutoTrade] = useState<boolean>(false);
  const [backtestRunning, setBacktestRunning] = useState(false);
  const [backtestResults, setBacktestResults] = useState<any>(null);
  const [strategies, setStrategies] = useState<any[]>([]);

  // Load trading mode and strategies from API on mount
  useEffect(() => {
    const loadData = async () => {
      try {
        // Trading mode
        const res = await fetch(apiUrl("trading-mode"));
        if (res.ok) {
          const data = await res.json();
          setBroker(data.broker);
          setAutoTrade(data.autoTrade);
          localStorage.setItem("cfd_broker", data.broker);
          localStorage.setItem("cfd_autoTrade", String(data.autoTrade));
        }
        
        // Strategies with indicators
        const stratRes = await fetch("/api/strategies");
        if (stratRes.ok) {
          const stratData = await stratRes.json();
          setStrategies(stratData.strategies || []);
        }
      } catch (e) {
        console.error("Failed to load data:", e);
      }
    };
    loadData();
  }, []);

  // Apply theme CSS variables
  useEffect(() => {
    const root = document.documentElement;
    root.classList.remove("theme-original", "theme-black", "theme-daylight");
    root.classList.add(`theme-${theme}`);
    const colors = themes[theme].colors;
    root.style.setProperty("--bg-primary", colors.bgPrimary);
    root.style.setProperty("--bg-secondary", colors.bgSecondary);
    root.style.setProperty("--bg-tertiary", colors.bgTertiary);
    root.style.setProperty("--border", colors.border);
    root.style.setProperty("--border-light", colors.borderLight);
    root.style.setProperty("--text-primary", colors.textPrimary);
    root.style.setProperty("--text-secondary", colors.textSecondary);
    root.style.setProperty("--text-muted", colors.textMuted);
    root.style.setProperty("--accent", colors.accent);
    root.style.setProperty("--success", colors.success);
    root.style.setProperty("--danger", colors.danger);
    root.style.setProperty("--warning", colors.warning);
    root.style.setProperty("--chart-bg", colors.chartBg);
    root.style.setProperty("--grid-line", colors.gridLine);
    root.style.setProperty("--chart-text", colors.chartText);
    root.style.setProperty("--chart-candle-up", colors.chartCandleUp);
    root.style.setProperty("--chart-candle-down", colors.chartCandleDown);
  }, [theme]);

  // Listen for theme changes from Settings
  useEffect(() => {
    const handleThemeChange = (e: CustomEvent<ThemeName>) => {
      setTheme(e.detail);
    };
    window.addEventListener("themechange", handleThemeChange as EventListener);
    return () => window.removeEventListener("themechange", handleThemeChange as EventListener);
  }, []);

  useEffect(() => {
    localStorage.setItem("cfd_activeTab", activeTab);
  }, [activeTab]);
  useEffect(() => {
    localStorage.setItem("cfd_selectedSymbol", selectedSymbol);
  }, [selectedSymbol]);

  useEffect(() => {
    localStorage.setItem("cfd_broker", broker);
  }, [broker]);

  useEffect(() => {
    localStorage.setItem("cfd_autoTrade", String(autoTrade));
  }, [autoTrade]);

  useEffect(() => {
    const timeInterval = setInterval(() => {
      setCurrentTime(new Date().toLocaleTimeString("en-GB", { timeZone: "Europe/Warsaw" }));
    }, 1000);

    const fetchData = async () => {
      try {
        const [logsRes, accRes] = await Promise.all([
          fetch(apiUrl("logs")),
          fetch(apiUrl("account")),
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
        console.error("Failed to fetch data:", error);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 5000); // Refresh every 5 seconds

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

  const tabs: Array<{
    id: TabType;
    label: string;
    shortLabel: string;
    icon: string;
  }> = [
    { id: "main", label: "Dashboard", shortLabel: "Home", icon: "◎" },
    { id: "charts", label: "Charts", shortLabel: "Charts", icon: "◩" },
    { id: "trades", label: "Trades", shortLabel: "Trades", icon: "⇅" },
    { id: "news", label: "News", shortLabel: "News", icon: "◉" },
    { id: "backtest", label: "Backtest", shortLabel: "Back", icon: "⏪" },
    { id: "console", label: "Console", shortLabel: "Log", icon: "▸" },
    { id: "settings", label: "Settings", shortLabel: "Set.", icon: "⚙" },
  ];

  return (
    <div
      className="w-full h-screen flex flex-col"
      style={{ backgroundColor: "var(--bg-primary)" }}
    >
      {/* Top Header Bar */}
      <div
        className="flex items-center justify-between px-3 md:px-5 py-2 md:py-2.5 flex-shrink-0"
        style={{
          backgroundColor: "var(--bg-secondary)",
          borderBottom: "1px solid var(--bg-tertiary)",
        }}
      >
        <div className="flex items-center gap-2 md:gap-4">
          {/* Mobile sidebar toggle */}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="md:hidden flex items-center justify-center w-7 h-7 rounded-sm"
            style={{
              backgroundColor: sidebarOpen ? "var(--bg-tertiary)" : "transparent",
              color: "var(--text-muted)",
            }}
          >
            <span className="text-sm">{sidebarOpen ? "✕" : "☰"}</span>
          </button>

          <div className="flex items-center gap-2">
            <div
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: "var(--success)" }}
            />
            <span
              className="text-xs font-bold tracking-wider uppercase hidden sm:inline"
              style={{ color: "var(--text-primary)", letterSpacing: "0.15em" }}
            >
              CFD Trading Bot
            </span>
            <span
              className="text-xs font-bold tracking-wider uppercase sm:hidden"
              style={{ color: "var(--text-primary)", letterSpacing: "0.15em" }}
            >
              CFD Bot
            </span>
          </div>
          <span
            className="text-[10px] px-2 py-0.5 rounded-sm font-medium hidden sm:inline-block"
            style={{ backgroundColor: "var(--bg-tertiary)", color: "var(--text-muted)" }}
          >
            v0.4.0
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
                color: activeTab === tab.id ? "var(--text-primary)" : "#4a5568",
                backgroundColor:
                  activeTab === tab.id ? "var(--bg-tertiary)" : "transparent",
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-4">
          <span
            className="text-[11px] font-medium hidden sm:inline"
            style={{ color: "#4a5568" }}
          >
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
            style={{ backgroundColor: "rgba(0,0,0,0.6)", top: "44px" }}
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* Sidebar - hidden on mobile, slides in when toggled */}
        <div
          className={`
          ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}
          md:translate-x-0 md:relative
          fixed top-[18px] left-0 bottom-[52px] md:bottom-0
          z-50 transition-transform duration-200 ease-in-out
        `}
        >
          <Sidebar 
              accountData={accountData} 
              broker={broker}
              autoTrade={autoTrade}
              onBrokerChange={setBroker}
              onAutoTradeChange={setAutoTrade}
            />
        </div>

        {/* Tab Content */}
        <div className="flex-1 overflow-hidden flex flex-col min-h-0">
          {activeTab === "main" && (
            <MainTab
              onSignalClick={(signal) => console.log("Signal clicked:", signal)}
              selectedSymbol={selectedSymbol}
              onSymbolSelect={setSelectedSymbol}
            />
          )}
          {activeTab === "charts" && <ChartsTab />}
          {activeTab === "trades" && <TradesTab />}
          {activeTab === "news" && <NewsTab />}
          {activeTab === "backtest" && (
            <div className="p-4">
              <h2 className="text-lg font-bold mb-4" style={{ color: "var(--text-primary)" }}>Backtest</h2>
              <div className="flex flex-wrap gap-4 mb-4">
                <div>
                  <label className="text-xs block mb-1" style={{ color: "var(--text-muted)" }}>Symbol</label>
                  <select
                    id="backtest-symbol"
                    className="p-2 rounded text-sm"
                    style={{ backgroundColor: "var(--bg-tertiary)", color: "var(--text-primary)", border: "1px solid var(--border)" }}
                  >
                    <option value="XAU">XAU (Gold)</option>
                    <option value="XAG">XAG (Silver)</option>
                    <option value="US100">US100 (Nasdaq)</option>
                    <option value="BTC">BTC (Bitcoin)</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs block mb-1" style={{ color: "var(--text-muted)" }}>Strategy</label>
                  <select
                    id="backtest-strategy"
                    className="p-2 rounded text-sm"
                    style={{ backgroundColor: "var(--bg-tertiary)", color: "var(--text-primary)", border: "1px solid var(--border)" }}
                    onChange={(e) => {
                      // Auto-select default indicators when strategy changes
                      const selectedStrat = strategies.find(s => s.id === e.target.value);
                      if (selectedStrat) {
                        const defaultInds = selectedStrat.default_indicators || [];
                        const allInds = ["RSI", "MACD", "BB", "SMA", "ADX", "STOCH", "MOMENTUM"];
                        allInds.forEach(ind => {
                          const cb = document.getElementById(`backtest-ind-${ind}`) as HTMLInputElement;
                          if (cb) cb.checked = defaultInds.includes(ind);
                        });
                      }
                    }}
                  >
                    <option value="">Default (per-symbol)</option>
                    {strategies.map(s => (
                      <option key={s.id} value={s.id}>{s.name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-xs block mb-1" style={{ color: "var(--text-muted)" }}>Indicators</label>
                  <div className="flex flex-wrap gap-2 text-xs">
                    {["RSI", "MACD", "BB", "SMA", "ADX", "STOCH", "MOMENTUM"].map(ind => (
                      <label key={ind} className="flex items-center gap-1 cursor-pointer">
                        <input type="checkbox" id={`backtest-ind-${ind}`} defaultChecked className="cursor-pointer" />
                        <span style={{ color: "var(--text-primary)" }}>{ind}</span>
                      </label>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="text-xs block mb-1" style={{ color: "var(--text-muted)" }}>Resolution</label>
                  <select
                    id="backtest-resolution"
                    className="p-2 rounded text-sm"
                    style={{ backgroundColor: "var(--bg-tertiary)", color: "var(--text-primary)", border: "1px solid var(--border)" }}
                  >
                    <option value="5">5m</option>
                    <option value="15">15m</option>
                    <option value="60">1H</option>
                    <option value="D">1D</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs block mb-1" style={{ color: "var(--text-muted)" }}>Days</label>
                  <input
                    id="backtest-days"
                    type="number"
                    defaultValue="14"
                    className="p-2 rounded text-sm w-20"
                    style={{ backgroundColor: "var(--bg-tertiary)", color: "var(--text-primary)", border: "1px solid var(--border)" }}
                  />
                </div>
                <div>
                  <label className="text-xs block mb-1" style={{ color: "var(--text-muted)" }}>Min Score</label>
                  <input
                    id="backtest-min-score"
                    type="number"
                    step="0.05"
                    defaultValue="0.1"
                    className="p-2 rounded text-sm w-20"
                    style={{ backgroundColor: "var(--bg-tertiary)", color: "var(--text-primary)", border: "1px solid var(--border)" }}
                  />
                </div>
                <div className="flex items-end gap-2">
                  <button
                    onClick={async () => {
                      const symbol = (document.getElementById("backtest-symbol") as HTMLSelectElement).value;
                      const strategy = (document.getElementById("backtest-strategy") as HTMLSelectElement).value;
                      // Get checked indicators
                      const allInds = ["RSI", "MACD", "BB", "SMA", "ADX", "STOCH", "MOMENTUM"];
                      const selectedInds = allInds.filter(ind => (document.getElementById(`backtest-ind-${ind}`) as HTMLInputElement)?.checked);
                      const indicators = selectedInds.join(",");
                      const resolution = (document.getElementById("backtest-resolution") as HTMLSelectElement).value;
                      const days = (document.getElementById("backtest-days") as HTMLInputElement).value;
                      const minScore = (document.getElementById("backtest-min-score") as HTMLInputElement).value;
                      
                      let url = `/api/backtest?symbol=${symbol}&resolution=${resolution}&days=${days}&min_score=${minScore}`;
                      if (strategy) url += `&strategy=${strategy}`;
                      if (indicators) url += `&indicators=${indicators}`;
                      
                      setBacktestRunning(true);
                      try {
                        const res = await fetch(url);
                        const data = await res.json();
                        setBacktestResults(data);
                      } catch (e) {
                        console.error(e);
                      }
                      setBacktestRunning(false);
                    }}
                    className="px-4 py-2 rounded text-sm font-bold"
                    style={{ backgroundColor: "var(--primary)", color: "white" }}
                  >
                    {backtestRunning ? "Running..." : "Run"}
                  </button>
                  <button
                    onClick={async () => {
                      const symbol = (document.getElementById("backtest-symbol") as HTMLSelectElement).value;
                      const resolution = (document.getElementById("backtest-resolution") as HTMLSelectElement).value;
                      const days = (document.getElementById("backtest-days") as HTMLInputElement).value;
                      const minScore = (document.getElementById("backtest-min-score") as HTMLInputElement).value;
                      
                      setBacktestRunning(true);
                      try {
                        const res = await fetch(`/api/backtest/optimize?symbol=${symbol}&resolution=${resolution}&days=${days}&min_score=${minScore}`);
                        const data = await res.json();
                        setBacktestResults({ optimize: data });
                      } catch (e) {
                        console.error(e);
                      }
                      setBacktestRunning(false);
                    }}
                    className="px-4 py-2 rounded text-sm font-bold"
                    style={{ backgroundColor: "var(--accent)", color: "white" }}
                  >
                    {backtestRunning ? "Optimizing..." : "Optimize"}
                  </button>
                </div>
              </div>
              
              {backtestResults && (
                <div className="mt-4">
                  {/* Optimize results */}
                  {backtestResults.optimize && (
                    <div className="mb-4">
                      <h3 className="text-md font-bold mb-2" style={{ color: "var(--accent)" }}>Optimization Results</h3>
                      <div className="p-3 rounded mb-3" style={{ backgroundColor: "var(--bg-secondary)", border: "1px solid var(--accent)" }}>
                        <div className="text-xs mb-1" style={{ color: "var(--text-muted)" }}>Best Combination</div>
                        <div className="flex gap-4 text-sm">
                          <div><span style={{ color: "var(--text-muted)" }}>Strategy:</span> <span style={{ color: "var(--success)" }}>{backtestResults.optimize.best?.strategy}</span></div>
                          <div><span style={{ color: "var(--text-muted)" }}>Indicators:</span> <span style={{ color: "var(--success)" }}>{(backtestResults.optimize.best?.indicators || []).join(", ")}</span></div>
                          <div><span style={{ color: "var(--text-muted)" }}>P&L:</span> <span style={{ color: backtestResults.optimize.best?.total_pnl >= 0 ? "var(--success)" : "var(--danger)" }}>${backtestResults.optimize.best?.total_pnl?.toFixed(2)}</span></div>
                          <div><span style={{ color: "var(--text-muted)" }}>Win Rate:</span> <span style={{ color: "var(--text-primary)" }}>{backtestResults.optimize.best?.win_rate}%</span></div>
                        </div>
                      </div>
                      <div className="text-xs mb-2" style={{ color: "var(--text-muted)" }}>Top 10 combinations:</div>
                      <div className="overflow-x-auto">
                        <table className="w-full text-xs">
                          <thead>
                            <tr style={{ borderBottom: "1px solid var(--border)" }}>
                              <th className="p-2 text-left" style={{ color: "var(--text-muted)" }}>#</th>
                              <th className="p-2 text-left" style={{ color: "var(--text-muted)" }}>Strategy</th>
                              <th className="p-2 text-left" style={{ color: "var(--text-muted)" }}>Indicators</th>
                              <th className="p-2 text-right" style={{ color: "var(--text-muted)" }}>Trades</th>
                              <th className="p-2 text-right" style={{ color: "var(--text-muted)" }}>P&L</th>
                              <th className="p-2 text-right" style={{ color: "var(--text-muted)" }}>Win Rate</th>
                              <th className="p-2 text-right" style={{ color: "var(--text-muted)" }}>Max DD</th>
                            </tr>
                          </thead>
                          <tbody>
                            {(backtestResults.optimize.results || []).slice(0, 10).map((r: any, i: number) => (
                              <tr key={i} style={{ borderBottom: "1px solid var(--bg-tertiary)" }}>
                                <td className="p-2" style={{ color: i === 0 ? "var(--accent)" : "var(--text-muted)" }}>{i + 1}</td>
                                <td className="p-2" style={{ color: "var(--text-primary)" }}>{r.strategy}</td>
                                <td className="p-2" style={{ color: "var(--text-primary)" }}>{r.indicators?.join(", ")}</td>
                                <td className="p-2 text-right" style={{ color: "var(--text-primary)" }}>{r.trades_count}</td>
                                <td className="p-2 text-right" style={{ color: r.total_pnl >= 0 ? "var(--success)" : "var(--danger)" }}>${r.total_pnl?.toFixed(2)}</td>
                                <td className="p-2 text-right" style={{ color: "var(--text-primary)" }}>{r.win_rate}%</td>
                                <td className="p-2 text-right" style={{ color: "var(--danger)" }}>{r.max_drawdown_pct}%</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                  
                  {/* Single backtest results */}
                  {!backtestResults.optimize && backtestResults.config && (
                    <>
                      <div className="mb-4 p-3 rounded" style={{ backgroundColor: "var(--bg-secondary)", border: "1px solid var(--border)" }}>
                        <div className="text-xs mb-2" style={{ color: "var(--text-muted)" }}>Configuration</div>
                        <div className="flex flex-wrap gap-4 text-sm">
                          <div>
                            <span style={{ color: "var(--text-muted)" }}>Strategy:</span>{" "}
                            <span style={{ color: "var(--text-primary)" }}>{backtestResults.config?.strategy}</span>
                          </div>
                          <div>
                            <span style={{ color: "var(--text-muted)" }}>Used:</span>{" "}
                            <span style={{ color: "var(--accent)" }}>{(backtestResults.config?.used_indicators || []).join(", ")}</span>
                          </div>
                          {backtestResults.config?.default_indicators && backtestResults.config?.used_indicators?.join(",") !== backtestResults.config?.default_indicators?.join(",") && (
                            <div>
                              <span style={{ color: "var(--text-muted)" }}>Default:</span>{" "}
                              <span style={{ color: "var(--text-muted)" }}>{backtestResults.config?.default_indicators?.join(", ")}</span>
                            </div>
                          )}
                        </div>
                      </div>
                      
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                    <div className="p-3 rounded" style={{ backgroundColor: "var(--bg-secondary)", border: "1px solid var(--border)" }}>
                      <div className="text-xs" style={{ color: "var(--text-muted)" }}>Total P&L</div>
                      <div className="text-xl font-bold" style={{ color: backtestResults.metrics?.total_pnl >= 0 ? "var(--success)" : "var(--danger)" }}>
                        ${backtestResults.metrics?.total_pnl?.toFixed(2)}
                      </div>
                    </div>
                    <div className="p-3 rounded" style={{ backgroundColor: "var(--bg-secondary)", border: "1px solid var(--border)" }}>
                      <div className="text-xs" style={{ color: "var(--text-muted)" }}>Win Rate</div>
                      <div className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>
                        {backtestResults.metrics?.win_rate}%
                      </div>
                    </div>
                    <div className="p-3 rounded" style={{ backgroundColor: "var(--bg-secondary)", border: "1px solid var(--border)" }}>
                      <div className="text-xs" style={{ color: "var(--text-muted)" }}>Trades</div>
                      <div className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>
                        {backtestResults.metrics?.trades_count}
                      </div>
                    </div>
                    <div className="p-3 rounded" style={{ backgroundColor: "var(--bg-secondary)", border: "1px solid var(--border)" }}>
                      <div className="text-xs" style={{ color: "var(--text-muted)" }}>Max DD</div>
                      <div className="text-xl font-bold" style={{ color: "var(--danger)" }}>
                        {backtestResults.metrics?.max_drawdown_pct}%
                      </div>
                    </div>
                  </div>
                  
                  <div className="text-xs mb-2" style={{ color: "var(--text-muted)" }}>
                    Period: {backtestResults.period?.from} to {backtestResults.period?.to}
                  </div>
                  </>
                  )}
                </div>
              )}
            </div>
          )}
          {activeTab === "console" && (
            <div className="flex-1 min-h-0 h-full">
              <ConsoleTab
                logs={logs && logs.length > 0 ? logs : undefined}
                maxLogs={100}
              />
            </div>
          )}
          {activeTab === "settings" && <SettingsTab/>}
        </div>
      </div>

      {/* Mobile Bottom Navigation */}
      <div
        className="md:hidden flex items-center justify-around flex-shrink-0"
        style={{
          backgroundColor: "var(--bg-secondary)",
          borderTop: "1px solid var(--bg-tertiary)",
          paddingBottom: "env(safe-area-inset-bottom, 0px)",
        }}
      >
        {tabs.slice(0, 5).map((tab) => (
          <button
            key={tab.id}
            onClick={() => handleTabSwitch(tab.id)}
            className="flex flex-col items-center py-2 px-2 min-w-[52px] transition-all"
            style={{
              color: activeTab === tab.id ? "var(--text-primary)" : "#4a5568",
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
        style={{
          backgroundColor: "var(--bg-secondary)",
          borderTop: "1px solid var(--bg-tertiary)",
          color: "#374151",
        }}
      >
        <span>CFD Trading Bot | XAU, XAG, US100, BTC</span>
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1">
            <span
              className="w-1.5 h-1.5 rounded-full"
              style={{ backgroundColor: "var(--success)" }}
            />
            Connected
          </span>
        </div>
      </div>
    </div>
  );
};
