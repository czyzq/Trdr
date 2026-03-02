import React, { useState, useEffect } from "react";
import { apiUrl } from "../api";
import { themes, ThemeName, getStoredTheme, setStoredTheme } from "../theme";

interface Setting {
  key: string;
  value: number;
  note: string;
}

interface FormData {
  key: string;
  value: number;
  note: string;
}

export const SettingsTab: React.FC = () => {
  const [settings, setSettings] = useState<Setting[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [form, setForm] = useState<FormData>({ key: "", value: 0, note: "" });
  const [currentTheme, setCurrentTheme] = useState<ThemeName>(getStoredTheme());

  const handleThemeChange = (theme: ThemeName) => {
    setCurrentTheme(theme);
    setStoredTheme(theme);
    // Dispatch event so other components can update
    window.dispatchEvent(new CustomEvent("themechange", { detail: theme }));
  };

  const fetchSettings = async (): Promise<void> => {
    setLoading(true);
    try {
      const res = await fetch(apiUrl("settings"));
      if (!res.ok) throw new Error("Failed to fetch");
      const data = await res.json();
      setSettings(
        Object.entries(data).map(([key, value]) => ({
        key,
        value: parseFloat(String(value)) || 0,
        note: "",
        })),
      );
    } catch (e) {
      console.error("Fetch error:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSettings().catch(console.error);
  }, []);

  const openModal = (key?: string): void => {
    if (key) {
      const s = settings.find((s) => s.key === key);
      if (s) setForm({ key: s.key, value: s.value, note: s.note });
      setEditingKey(key);
    } else {
      setForm({ key: "", value: 0, note: "" });
      setEditingKey(null);
    }
    setModalOpen(true);
  };

  const closeModal = (): void => {
    setModalOpen(false);
    setEditingKey(null);
    setForm({ key: "", value: 0, note: "" });
  };

  const saveSetting = async (): Promise<void> => {
    try {
      const res = await fetch(apiUrl("settings"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (res.ok) {
        fetchSettings();
        closeModal();
      } else {
        alert("Save failed");
      }
    } catch (e) {
      console.error(e);
      alert("Save error");
    }
  };

  const deleteSetting = async (key: string): Promise<void> => {
    if (!confirm(`Delete setting "${key}"?`)) return;
    try {
      const res = await fetch(apiUrl(`settings/${key}`), { method: "DELETE" });
      if (res.ok) {
        fetchSettings();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const refresh = (): void => {
    fetchSettings();
  };

  return (
    <div
      className="h-full flex flex-col p-4 md:p-6 bg-[var(--bg-primary)]"
      style={{ color: "var(--text-primary)" }}
    >
      {/* Dynamic Positions Status */}
      <div style={{ 
        background: "rgba(0,255,136,0.1)", 
        border: "1px solid #00ff88", 
        borderRadius: "8px", 
        padding: "12px",
        marginBottom: "20px"
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <span>🎯</span>
          <div>
            <strong>Dynamic Positions</strong>
            <div style={{ fontSize: "11px", color: "#888" }}>
              Auto-zamykanie przy spadku sygnału &gt;25%
            </div>
          </div>
          <span style={{ 
            background: "#00ff88", 
            color: "#000", 
            padding: "2px 8px", 
            borderRadius: "4px",
            fontSize: "11px",
            marginLeft: "auto"
          }}>ON</span>
        </div>
      </div>

      <div className="flex items-center justify-between mb-4 md:mb-6">
        <h2 className="text-lg md:text-xl font-bold uppercase tracking-wider text-[var(--text-primary)]">
          Settings
        </h2>
        <div className="flex gap-2">
          <button
            onClick={() => openModal()}
            className="px-3 py-1.5 text-xs bg-[var(--bg-tertiary)]/50 hover:bg-[var(--success)]/70 rounded border border-[var(--border-light)]/50 text-[var(--text-primary)] transition-all font-medium"
          >
            Add New
          </button>
          <button
            onClick={refresh}
            className="px-3 py-1.5 text-xs bg-[var(--bg-tertiary)]/50 hover:bg-blue-500/70 rounded border border-[var(--border-light)]/50 text-[var(--text-primary)] transition-all font-medium"
            disabled={loading}
          >
            {loading ? "Loading..." : "Refresh"}
          </button>
        </div>
      </div>

      {/* Theme Selector */}
      <div className="mb-4 p-4 rounded-lg border" style={{ backgroundColor: "var(--bg-secondary)", borderColor: "var(--bg-tertiary)" }}>
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">Theme</h3>
            <p className="text-xs text-[var(--text-muted)] mt-0.5">Choose your color scheme</p>
          </div>
          <div className="flex gap-2">
            {(Object.keys(themes) as ThemeName[]).map((themeName) => (
              <button
                key={themeName}
                onClick={() => handleThemeChange(themeName)}
                className="px-3 py-1.5 text-xs rounded border transition-all font-medium"
                style={{
                  backgroundColor: currentTheme === themeName ? themes[themeName].colors.bgTertiary : "transparent",
                  borderColor: currentTheme === themeName ? themes[themeName].colors.accent : "var(--border-light)",
                  color: currentTheme === themeName ? themes[themeName].colors.textPrimary : "var(--text-muted)",
                }}
              >
                {themes[themeName].displayName}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-auto border border-[var(--bg-tertiary)]/50 rounded-lg bg-[var(--bg-secondary)]/50">
        <div className="p-4">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: "1px solid var(--bg-tertiary)" }}>
                  <th className="py-3 text-left font-semibold text-[var(--text-muted)] pr-4 min-w-[120px]">
                    Parameter
                  </th>
                  <th className="py-3 text-left font-semibold text-[var(--text-muted)] pr-4 min-w-[100px]">
                    Value
                  </th>
                  <th className="py-3 text-left font-semibold text-[var(--text-muted)] pr-8 min-w-[150px]">
                    Note
                  </th>
                  <th className="py-3 text-right font-semibold text-[var(--text-muted)] w-32">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {settings.length === 0 ? (
                  <tr>
                    <td
                      colSpan={4}
                      className="py-12 text-center opacity-60"
                      style={{ color: "#4a5568" }}
                    >
                      No settings configured. Click "Add New" to create your
                      first setting.
                    </td>
                  </tr>
                ) : (
                  settings.map((s) => (
                    <tr
                      key={s.key}
                      style={{ borderBottom: "1px solid rgba(26,31,53,0.5)" }}
                    >
                      <td className="py-3 font-mono text-[var(--text-primary)] font-medium">
                        {s.key}
                      </td>
                      <td className="py-3 font-mono text-[var(--text-primary)] bg-[var(--bg-tertiary)]/30 px-2 py-1 rounded">
                        {Number.isInteger(s.value) ? s.value : s.value.toFixed(2)}
                      </td>
                      <td className="py-3 pr-8 text-[var(--text-secondary)]">{s.note}</td>
                      <td className="py-3 text-right">
                        <div className="flex justify-end gap-2">
                          <button
                            onClick={() => openModal(s.key)}
                            className="text-xs px-2 py-1 rounded hover:bg-blue-500/20 text-blue-400 hover:text-blue-300 transition font-medium"
                          >
                            Edit
                          </button>
                          <button
                            onClick={() => deleteSetting(s.key)}
                            className="text-xs px-2 py-1 rounded hover:bg-red-500/20 text-red-400 hover:text-red-300 transition font-medium"
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="bg-[var(--bg-secondary)] w-full max-w-md rounded-xl shadow-2xl border border-[var(--bg-tertiary)]/50 max-h-[85vh] overflow-hidden">
            <div className="p-6 border-b border-[var(--bg-tertiary)]/50">
              <div className="flex items-center justify-between">
                <h3
                  className="text-lg font-bold tracking-wide"
                  style={{ color: "var(--text-primary)" }}
                >
                  {editingKey ? `Edit ${form.key}` : "Add New Setting"}
                </h3>
                <button
                  onClick={closeModal}
                  className="p-1.5 rounded-lg hover:bg-[var(--bg-tertiary)] transition-all"
                  style={{ color: "var(--text-muted)" }}
                >
                  ×
                </button>
              </div>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label
                  className="block text-xs font-medium mb-2 uppercase tracking-wider"
                  style={{ color: "var(--text-secondary)" }}
                >
                  Key
                </label>
                <input
                  type="text"
                  value={form.key}
                  onChange={(e) => setForm({ ...form, key: e.target.value })}
                  className="w-full px-3 py-2.5 bg-[var(--bg-tertiary)] border border-[var(--border-light)]/50 rounded-lg text-sm focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20 transition-all"
                  style={{ color: "var(--text-primary)" }}
                  placeholder="e.g. max_risk_pct"
                  disabled={!!editingKey}
                />
              </div>
              <div>
                <label
                  className="block text-xs font-medium mb-2 uppercase tracking-wider"
                  style={{ color: "var(--text-secondary)" }}
                >
                  Value
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={form.value}
                  onChange={(e) =>
                    setForm({ ...form, value: parseFloat(e.target.value) || 0 })
                  }
                  className="w-full px-3 py-2.5 bg-[var(--bg-tertiary)] border border-[var(--border-light)]/50 rounded-lg text-sm focus:border-green-500/50 focus:ring-1 focus:ring-green-500/20 transition-all"
                  style={{ color: "var(--text-primary)" }}
                  placeholder="e.g. 2.0"
                />
              </div>
              <div>
                <label
                  className="block text-xs font-medium mb-2 uppercase tracking-wider"
                  style={{ color: "var(--text-secondary)" }}
                >
                  Note
                </label>
                <textarea
                  rows={3}
                  value={form.note}
                  onChange={(e) => setForm({ ...form, note: e.target.value })}
                  className="w-full px-3 py-2.5 bg-[var(--bg-tertiary)] border border-[var(--border-light)]/50 rounded-lg text-sm resize-vertical focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 transition-all"
                  style={{ color: "var(--text-primary)" }}
                  placeholder="Optional description..."
                />
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  onClick={saveSetting}
                  disabled={!form.key.trim()}
                  className="flex-1 px-4 py-2.5 bg-gradient-to-r from-green-500/90 to-emerald-500/90 hover:from-green-600 hover:to-emerald-600 text-white font-semibold text-xs uppercase tracking-wider rounded-lg shadow-lg transition-all disabled:from-gray-600/50 disabled:to-gray-600/50 disabled:cursor-not-allowed disabled:shadow-none flex items-center justify-center h-11"
                >
                  Save Setting
                </button>
                <button
                  onClick={closeModal}
                  className="flex-1 px-4 py-2.5 bg-[var(--bg-tertiary)]/50 hover:bg-[var(--bg-tertiary)] border border-[var(--border-light)]/50 text-[var(--text-secondary)] hover:text-[var(--text-primary)] font-semibold text-xs uppercase tracking-wider rounded-lg shadow-lg transition-all flex items-center justify-center h-11"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
