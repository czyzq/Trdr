import React, { useState, useEffect } from 'react';
import { apiUrl } from '../api';

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
  const [form, setForm] = useState<FormData>({key: '', value: 0, note: ''});

  const fetchSettings = async (): Promise<void> => {
    setLoading(true);
    try {
      const res = await fetch(apiUrl('settings'));
      if (!res.ok) throw new Error('Failed to fetch');
      const data = await res.json() as { settings: Setting[] };
      setSettings(data.settings.map((s: Setting) => ({
        key: s.key || '',
        value: Number(s.value) || 0,
        note: s.note || '',
      })));
    } catch (e) {
      console.error('Fetch error:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSettings();
  }, []);

  const openModal = (key?: string): void => {
    if (key) {
      const s = settings.find(s => s.key === key);
      if (s) setForm({key: s.key, value: s.value, note: s.note});
      setEditingKey(key);
    } else {
      setForm({key: '', value: 0, note: ''});
      setEditingKey(null);
    }
    setModalOpen(true);
  };

  const closeModal = (): void => {
    setModalOpen(false);
    setEditingKey(null);
    setForm({key: '', value: 0, note: ''});
  };

  const saveSetting = async (): Promise<void> => {
    try {
      const res = await fetch(apiUrl('settings'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(form)
      });
      if (res.ok) {
        fetchSettings();
        closeModal();
      } else {
        alert('Save failed');
      }
    } catch (e) {
      console.error(e);
      alert('Save error');
    }
  };

  const deleteSetting = async (key: string): Promise<void> => {
    if (!confirm(`Delete setting "${key}"?`)) return;
    try {
      const res = await fetch(apiUrl(`settings/${key}`), {method: 'DELETE'});
      if (res.ok) {
        fetchSettings();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const refresh = (): void => fetchSettings();

  return (
    <div className="h-full flex flex-col p-4 md:p-6 bg-[#0b0f1a]" style={{color: '#e2e8f0'}}>
      <div className="flex items-center justify-between mb-4 md:mb-6">
        <h2 className="text-lg md:text-xl font-bold uppercase tracking-wider text-[#e2e8f0]">Settings</h2>
        <div className="flex gap-2">
          <button 
            onClick={() => openModal()} 
            className="px-3 py-1.5 text-xs bg-[#1a1f35]/50 hover:bg-[#22c55e]/70 rounded border border-[#2a3349]/50 text-[#e2e8f0] transition-all font-medium"
          >
            Add New
          </button>
          <button 
            onClick={refresh} 
            className="px-3 py-1.5 text-xs bg-[#1a1f35]/50 hover:bg-blue-500/70 rounded border border-[#2a3349]/50 text-[#e2e8f0] transition-all font-medium" 
            disabled={loading}
          >
            {loading ? 'Loading...' : 'Refresh'}
          </button>
        </div>
      </div>
      <div className="flex-1 overflow-auto border border-[#1a1f35]/50 rounded-lg bg-[#0d1220]/50">
        <div className="p-4">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{borderBottom: '1px solid #1a1f35'}}>
                  <th className="py-3 text-left font-semibold text-[#64748b] pr-4 min-w-[120px]">Parameter</th>
                  <th className="py-3 text-left font-semibold text-[#64748b] pr-4 min-w-[100px]">Value</th>
                  <th className="py-3 text-left font-semibold text-[#64748b] pr-8 min-w-[150px]">Note</th>
                  <th className="py-3 text-right font-semibold text-[#64748b] w-32">Actions</th>
                </tr>
              </thead>
              <tbody>
                {settings.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="py-12 text-center opacity-60" style={{color: '#4a5568'}}>
                      No settings configured. Click "Add New" to create your first setting.
                    </td>
                  </tr>
                ) : (
                  settings.map((s) => (
                    <tr key={s.key} style={{borderBottom: '1px solid rgba(26,31,53,0.5)'}}>
                      <td className="py-3 font-mono text-[#e2e8f0] font-medium">{s.key}</td>
                      <td className="py-3 font-mono text-[#e2e8f0] bg-[#1a1f35]/30 px-2 py-1 rounded">{s.value.toFixed(2)}</td>
                      <td className="py-3 pr-8 text-[#9ca3af]">{s.note}</td>
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
      {modalOpen &amp;&amp;&amp;&amp;&amp;&amp;&amp;&amp;&amp;&amp;&amp;&amp;&amp;&amp;&amp;&amp; (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="bg-[#0d1220] w-full max-w-md rounded-xl shadow-2xl border border-[#1a1f35]/50 max-h-[85vh] overflow-hidden">
            <div className="p-6 border-b border-[#1a1f35]/50">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold tracking-wide" style={{color: '#e2e8f0'}}>
                  {editingKey ? `Edit ${form.key}` : 'Add New Setting'}
                </h3>
                <button 
                  onClick={closeModal} 
                  className="p-1.5 rounded-lg hover:bg-[#1a1f35] transition-all" 
                  style={{color: '#64748b'}}
                >
                  ×
                </button>
              </div>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-medium mb-2 uppercase tracking-wider" style={{color: '#9ca3af'}}>Key</label>
                <input 
                  type="text" 
                  value={form.key}
                  onChange={(e) => setForm({...form, key: e.target.value})}
                  className="w-full px-3 py-2.5 bg-[#1a1f35] border border-[#2a3349]/50 rounded-lg text-sm focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20 transition-all" 
                  style={{color: '#e2e8f0'}}
                  placeholder="e.g. max_risk_pct"
                  disabled={!!editingKey}
                />
              </div>
              <div>
                <label className="block text-xs font-medium mb-2 uppercase tracking-wider" style={{color: '#9ca3af'}}>Value</label>
                <input 
                  type="number" 
                  step="0.01"
                  value={form.value}
                  onChange={(e) => setForm({...form, value: parseFloat(e.target.value) || 0})}
                  className="w-full px-3 py-2.5 bg-[#1a1f35] border border-[#2a3349]/50 rounded-lg text-sm focus:border-green-500/50 focus:ring-1 focus:ring-green-500/20 transition-all" 
                  style={{color: '#e2e8f0'}}
                  placeholder="e.g. 2.0"
                />
              </div>
              <div>
                <label className="block text-xs font-medium mb-2 uppercase tracking-wider" style={{color: '#9ca3af'}}>Note</label>
                <textarea 
                  rows={3}
                  value={form.note}
                  onChange={(e) => setForm({...form, note: e.target.value})}
                  className="w-full px-3 py-2.5 bg-[#1a1f35] border border-[#2a3349]/50 rounded-lg text-sm resize-vertical focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 transition-all" 
                  style={{color: '#e2e8f0'}}
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
                  className="flex-1 px-4 py-2.5 bg-[#1a1f35]/50 hover:bg-[#1a1f35] border border-[#2a3349]/50 text-[#9ca3af] hover:text-[#e2e8f0] font-semibold text-xs uppercase tracking-wider rounded-lg shadow-lg transition-all flex items-center justify-center h-11"
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