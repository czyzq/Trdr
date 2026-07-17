import React, { useCallback, useEffect, useState } from "react";
import { apiUrl } from "../api";
import { Card, SectionLabel, Badge, Toggle, EmptyState } from "./ui";
import { fmtDateTime } from "./format";

interface Study {
  strategy_id: string;
  symbol?: string;
  at?: string;
  passed?: boolean | null;
  best_value?: number | null;
}

interface StrategyVersion {
  strategy_id: string;
  version: number;
  status: string; // active / retired / rolled_back
  source?: string;
  created_at?: string;
}

interface OptimizerStatus {
  optimizer_enabled: boolean;
  auto_promote_enabled: boolean;
  studies: Study[];
  versions: StrategyVersion[];
}

const statusTone = (status: string): "green" | "slate" | "amber" => {
  if (status === "active") return "green";
  if (status === "rolled_back") return "amber";
  return "slate";
};

export const StrategyLabPage: React.FC = () => {
  const [status, setStatus] = useState<OptimizerStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [rollingBack, setRollingBack] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch(apiUrl("optimizer/status"));
      if (res.ok) {
        setStatus(await res.json());
        setError(null);
      } else {
        setError("Failed to load optimizer status");
      }
    } catch {
      setError("Failed to load optimizer status");
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 30000);
    return () => clearInterval(interval);
  }, [refresh]);

  const updateSetting = async (key: "optimizer_enabled" | "auto_promote_enabled", value: boolean) => {
    if (!status) return;
    setSaving(true);
    setStatus({ ...status, [key]: value });
    try {
      const res = await fetch(apiUrl("optimizer/settings"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ [key]: value }),
      });
      if (!res.ok) await refresh(); // revert to server truth
    } catch {
      await refresh();
    } finally {
      setSaving(false);
    }
  };

  const rollback = async (strategyId: string) => {
    if (!confirm(`Roll back strategy "${strategyId}" to its previous version?`)) return;
    setRollingBack(strategyId);
    try {
      const res = await fetch(apiUrl(`optimizer/rollback/${strategyId}`), { method: "POST" });
      const data = await res.json();
      if (!res.ok) alert(data.error || "Rollback failed");
      await refresh();
    } catch {
      alert("Rollback failed");
    } finally {
      setRollingBack(null);
    }
  };

  const activeStrategies = new Set(
    (status?.versions || []).filter((v) => v.status === "active").map((v) => v.strategy_id),
  );

  return (
    <div className="space-y-5">
      {/* Master switches */}
      <Card className="p-4 space-y-4">
        <SectionLabel>Self-optimization</SectionLabel>
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="text-sm font-medium text-slate-200">Optimizer</div>
            <div className="text-xs text-slate-500">Run nightly optimization studies</div>
          </div>
          <Toggle
            checked={Boolean(status?.optimizer_enabled)}
            onChange={(v) => updateSetting("optimizer_enabled", v)}
            disabled={saving || !status}
            label="Optimizer enabled"
          />
        </div>
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="text-sm font-medium text-slate-200">Auto-promote</div>
            <div className="text-xs text-slate-500">Guard-passing candidates go live automatically</div>
          </div>
          <Toggle
            checked={Boolean(status?.auto_promote_enabled)}
            onChange={(v) => updateSetting("auto_promote_enabled", v)}
            disabled={saving || !status}
            label="Auto-promote enabled"
          />
        </div>
      </Card>

      {error && (
        <Card>
          <EmptyState title={error} />
        </Card>
      )}

      {/* Recent studies */}
      <div>
        <SectionLabel className="mb-2">Recent studies</SectionLabel>
        {!status || status.studies.length === 0 ? (
          <Card>
            <EmptyState title="No optimization studies yet" hint="Nightly studies appear here" />
          </Card>
        ) : (
          <div className="space-y-2">
            {status.studies.map((s, i) => (
              <Card key={`${s.strategy_id}-${s.at}-${i}`} className="p-3.5">
                <div className="flex items-center justify-between gap-3 flex-wrap">
                  <div className="flex items-center gap-2.5">
                    <span className="text-sm font-semibold text-slate-100">{s.strategy_id}</span>
                    {s.symbol && <span className="text-xs text-slate-500">{s.symbol}</span>}
                    <Badge tone={s.passed ? "green" : "red"}>{s.passed ? "passed" : "failed"}</Badge>
                  </div>
                  <div className="flex items-center gap-4 text-xs text-slate-500 tabular-nums">
                    <span>
                      Best{" "}
                      <span className="text-slate-300">
                        {s.best_value !== null && s.best_value !== undefined ? Number(s.best_value).toFixed(4) : "–"}
                      </span>
                    </span>
                    <span>{fmtDateTime(s.at)}</span>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Versions */}
      <div>
        <SectionLabel className="mb-2">Strategy versions</SectionLabel>
        {!status || status.versions.length === 0 ? (
          <Card>
            <EmptyState title="No strategy versions" hint="Promotions create versions here" />
          </Card>
        ) : (
          <div className="space-y-2">
            {status.versions.map((v, i) => (
              <Card key={`${v.strategy_id}-${v.version}-${i}`} className="p-3.5">
                <div className="flex items-center justify-between gap-3 flex-wrap">
                  <div className="flex items-center gap-2.5">
                    <span className="text-sm font-semibold text-slate-100">{v.strategy_id}</span>
                    <span className="text-xs text-slate-500 tabular-nums">v{v.version}</span>
                    <Badge tone={statusTone(v.status)}>{v.status.replace("_", " ")}</Badge>
                    {v.source && <span className="text-xs text-slate-600">{v.source}</span>}
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-slate-500 tabular-nums">{fmtDateTime(v.created_at)}</span>
                    {activeStrategies.has(v.strategy_id) && v.status === "active" && (
                      <button
                        onClick={() => rollback(v.strategy_id)}
                        disabled={rollingBack === v.strategy_id}
                        className="px-3 py-1.5 rounded-lg border border-amber-400/30 bg-amber-400/10 text-amber-400 text-xs font-semibold hover:bg-amber-400/20 transition-colors disabled:opacity-50"
                      >
                        {rollingBack === v.strategy_id ? "Rolling back..." : "Rollback"}
                      </button>
                    )}
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
