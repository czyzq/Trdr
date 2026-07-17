import React from "react";

// Small shared building blocks for Dashboard v2.
// Design language: dark trading terminal - slate background, hairline
// borders, rounded-xl cards, tabular numbers, green/red P&L accents.

export const Card: React.FC<{ className?: string; children: React.ReactNode }> = ({
  className = "",
  children,
}) => (
  <div className={`rounded-xl border border-white/5 bg-[#101623] ${className}`}>
    {children}
  </div>
);

export const SectionLabel: React.FC<{ children: React.ReactNode; className?: string }> = ({
  children,
  className = "",
}) => (
  <div className={`text-[11px] font-medium uppercase tracking-widest text-slate-500 ${className}`}>
    {children}
  </div>
);

export const StatTile: React.FC<{
  label: string;
  value: string;
  valueClass?: string;
  sub?: string;
}> = ({ label, value, valueClass = "text-slate-100", sub }) => (
  <Card className="p-4">
    <SectionLabel>{label}</SectionLabel>
    <div className={`mt-1.5 text-xl md:text-2xl font-semibold tabular-nums ${valueClass}`}>
      {value}
    </div>
    {sub && <div className="mt-0.5 text-xs text-slate-500">{sub}</div>}
  </Card>
);

export const DirectionPill: React.FC<{ direction: string }> = ({ direction }) => {
  const d = (direction || "").toLowerCase();
  const isBuy = d.includes("buy") || d === "long";
  const isSell = d.includes("sell") || d === "short";
  const cls = isBuy
    ? "text-green-400 bg-green-400/10 border-green-400/20"
    : isSell
      ? "text-red-400 bg-red-400/10 border-red-400/20"
      : "text-slate-400 bg-slate-400/10 border-slate-400/20";
  return (
    <span className={`inline-block px-2 py-0.5 rounded-md border text-[11px] font-bold uppercase tracking-wide ${cls}`}>
      {direction?.replace("_", " ") || "?"}
    </span>
  );
};

export const Badge: React.FC<{
  children: React.ReactNode;
  tone?: "green" | "red" | "amber" | "slate" | "blue";
}> = ({ children, tone = "slate" }) => {
  const tones: Record<string, string> = {
    green: "text-green-400 bg-green-400/10 border-green-400/20",
    red: "text-red-400 bg-red-400/10 border-red-400/20",
    amber: "text-amber-400 bg-amber-400/10 border-amber-400/20",
    blue: "text-sky-400 bg-sky-400/10 border-sky-400/20",
    slate: "text-slate-400 bg-slate-400/10 border-slate-400/20",
  };
  return (
    <span className={`inline-block px-2 py-0.5 rounded-md border text-[11px] font-medium uppercase tracking-wide ${tones[tone]}`}>
      {children}
    </span>
  );
};

export const Toggle: React.FC<{
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  label?: string;
}> = ({ checked, onChange, disabled, label }) => (
  <button
    type="button"
    role="switch"
    aria-checked={checked}
    aria-label={label}
    disabled={disabled}
    onClick={() => onChange(!checked)}
    className={`relative inline-flex h-7 w-12 flex-shrink-0 items-center rounded-full border transition-colors duration-150 ${
      checked ? "bg-green-500/80 border-green-400/40" : "bg-slate-700/70 border-white/10"
    } ${disabled ? "opacity-40 cursor-not-allowed" : "cursor-pointer"}`}
  >
    <span
      className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform duration-150 ${
        checked ? "translate-x-6" : "translate-x-1"
      }`}
    />
  </button>
);

export const SymbolChips: React.FC<{
  symbols: string[];
  selected: string;
  onSelect: (s: string) => void;
}> = ({ symbols, selected, onSelect }) => (
  <div className="flex flex-wrap gap-2">
    {symbols.map((s) => (
      <button
        key={s}
        onClick={() => onSelect(s)}
        className={`px-3 py-1.5 rounded-lg border text-sm font-medium transition-colors ${
          selected === s
            ? "bg-slate-200/10 border-white/20 text-slate-100"
            : "bg-transparent border-white/5 text-slate-500 hover:text-slate-300"
        }`}
      >
        {s}
      </button>
    ))}
  </div>
);

export const EmptyState: React.FC<{ title: string; hint?: string }> = ({ title, hint }) => (
  <div className="py-12 text-center">
    <div className="text-sm text-slate-400">{title}</div>
    {hint && <div className="mt-1 text-xs text-slate-600">{hint}</div>}
  </div>
);

// Horizontal score bar for a [-1, 1] value with a center line.
export const ScoreBar: React.FC<{ score: number }> = ({ score }) => {
  const clamped = Math.max(-1, Math.min(1, score || 0));
  const half = Math.abs(clamped) * 50; // percent of half-width
  const positive = clamped >= 0;
  return (
    <div className="relative h-2.5 w-full rounded-full bg-slate-800 overflow-hidden">
      <div className="absolute inset-y-0 left-1/2 w-px bg-white/20" />
      <div
        className={`absolute inset-y-0 rounded-full ${positive ? "bg-green-400/80" : "bg-red-400/80"}`}
        style={
          positive
            ? { left: "50%", width: `${half}%` }
            : { right: "50%", width: `${half}%` }
        }
      />
    </div>
  );
};
