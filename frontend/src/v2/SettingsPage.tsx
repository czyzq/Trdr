import React, { useEffect, useState } from "react";
import { apiUrl } from "../api";
import { setUiVersion } from "../uiVersion";
import { Card, SectionLabel, Badge } from "./ui";
import { usePush } from "./usePush";

interface NotifierStatus {
  telegram_configured: boolean;
  imessage_available: boolean;
  push_subscriptions?: number;
}

interface Health {
  status: string;
  mongodb?: string;
  version?: string;
  timestamp?: string;
}

const PushRow: React.FC = () => {
  const { state, busy, subscribe, unsubscribe, sendTest } = usePush();

  const hint: Record<string, string> = {
    unsupported: "This browser does not support Web Push",
    "needs-install": "Add Trdr to your home screen first (Share → Add to Home Screen), then enable here",
    default: "Native push notifications on this device (iPhone/iPad: home-screen app, iOS 16.4+)",
    denied: "Notifications are blocked for this site in system settings",
    subscribed: "This device receives trade and optimizer notifications",
  };

  return (
    <div className="flex items-center justify-between gap-3">
      <div>
        <div className="text-sm font-medium text-slate-200">Push on this device</div>
        <div className="text-xs text-slate-500 mt-0.5">{hint[state]}</div>
      </div>
      {state === "subscribed" ? (
        <div className="flex gap-2 shrink-0">
          <button
            onClick={sendTest}
            className="px-3 py-2 rounded-lg border border-white/10 text-xs text-slate-200 hover:bg-white/5 transition-colors"
          >
            Test
          </button>
          <button
            onClick={unsubscribe}
            disabled={busy}
            className="px-3 py-2 rounded-lg border border-white/10 text-xs text-slate-400 hover:bg-white/5 transition-colors"
          >
            Disable
          </button>
        </div>
      ) : (
        <button
          onClick={subscribe}
          disabled={busy || state === "unsupported" || state === "denied" || state === "needs-install"}
          className="px-3 py-2 rounded-lg border border-white/10 text-sm text-slate-200 hover:bg-white/5 transition-colors disabled:opacity-40 whitespace-nowrap shrink-0"
        >
          {busy ? "..." : "Enable"}
        </button>
      )}
    </div>
  );
};

export const SettingsPage: React.FC = () => {
  const [notifier, setNotifier] = useState<NotifierStatus | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch(apiUrl("notifier/status"));
        if (res.ok) setNotifier(await res.json());
      } catch {
        /* leave null */
      }
      try {
        const res = await fetch("/health");
        if (res.ok) {
          setHealth(await res.json());
          setHealthError(false);
        } else {
          setHealthError(true);
        }
      } catch {
        setHealthError(true);
      }
    };
    load();
  }, []);

  return (
    <div className="space-y-5 max-w-2xl">
      {/* Interface version */}
      <Card className="p-4">
        <SectionLabel className="mb-3">Interface</SectionLabel>
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="text-sm font-medium text-slate-200">Dashboard version</div>
            <div className="text-xs text-slate-500 mt-0.5">
              You are using the new dashboard (v2). The classic dashboard remains fully functional.
            </div>
          </div>
          <button
            onClick={() => setUiVersion("classic")}
            className="px-3 py-2 rounded-lg border border-white/10 text-sm text-slate-200 hover:bg-white/5 transition-colors whitespace-nowrap"
          >
            Switch to classic dashboard
          </button>
        </div>
      </Card>

      {/* Notifications */}
      <Card className="p-4">
        <SectionLabel className="mb-3">Notifications</SectionLabel>
        <div className="space-y-3">
          <PushRow />
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-medium text-slate-200">Telegram</div>
              <div className="text-xs text-slate-500 mt-0.5">
                Configured via TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID on the backend
              </div>
            </div>
            <Badge tone={notifier?.telegram_configured ? "green" : "slate"}>
              {notifier === null ? "..." : notifier.telegram_configured ? "configured" : "not configured"}
            </Badge>
          </div>
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-medium text-slate-200">iMessage</div>
              <div className="text-xs text-slate-500 mt-0.5">Mac-only dispatcher via OpenClaw</div>
            </div>
            <Badge tone={notifier?.imessage_available ? "green" : "slate"}>
              {notifier === null ? "..." : notifier.imessage_available ? "available" : "unavailable"}
            </Badge>
          </div>
        </div>
      </Card>

      {/* Theme */}
      <Card className="p-4">
        <SectionLabel className="mb-3">Theme</SectionLabel>
        <p className="text-sm text-slate-400 leading-relaxed">
          Dashboard v2 uses a fixed dark trading-terminal theme optimized for readability on
          mobile and desktop. The classic dashboard's selectable themes are available after
          switching back to the classic interface.
        </p>
      </Card>

      {/* Backend health */}
      <Card className="p-4">
        <SectionLabel className="mb-3">Backend health</SectionLabel>
        {healthError ? (
          <div className="flex items-center gap-2.5">
            <span className="w-2.5 h-2.5 rounded-full bg-red-400" />
            <span className="text-sm text-red-400">Backend unreachable</span>
          </div>
        ) : !health ? (
          <div className="text-sm text-slate-500">Checking...</div>
        ) : (
          <div className="space-y-2 text-sm tabular-nums">
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Status</span>
              <span className="flex items-center gap-2 text-slate-200">
                <span className={`w-2 h-2 rounded-full ${health.status === "ok" ? "bg-green-400" : "bg-red-400"}`} />
                {health.status}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500">MongoDB</span>
              <span className={health.mongodb === "connected" ? "text-green-400" : "text-amber-400"}>
                {health.mongodb || "unknown"}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Version</span>
              <span className="text-slate-300">{health.version || "–"}</span>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
};
