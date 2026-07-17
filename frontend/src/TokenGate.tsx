/* Token gate: shown only when the backend requires auth (DASHBOARD_TOKEN set)
   and this browser has no valid token cookie yet. The token is stored as a
   cookie, so every existing fetch in both dashboards authenticates
   automatically - no per-request changes needed. */
import React, { useEffect, useState } from "react";
import { apiUrl } from "./api";

const COOKIE = "trdr_token";

function setTokenCookie(token: string) {
  const secure = window.location.protocol === "https:" ? "; Secure" : "";
  document.cookie = `${COOKIE}=${encodeURIComponent(token)}; Path=/; Max-Age=31536000; SameSite=Lax${secure}`;
}

export const TokenGate: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [status, setStatus] = useState<"checking" | "locked" | "open">("checking");
  const [token, setToken] = useState("");
  const [error, setError] = useState(false);

  useEffect(() => {
    fetch(apiUrl("auth/check"))
      .then((res) => setStatus(res.status === 401 ? "locked" : "open"))
      .catch(() => setStatus("open")); // backend down: let the app render its own error states
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setTokenCookie(token.trim());
    const res = await fetch(apiUrl("auth/check"));
    if (res.status === 401) {
      setError(true);
    } else {
      setStatus("open");
    }
  };

  if (status === "checking") {
    return <div className="min-h-screen bg-[#0b0f17]" />;
  }
  if (status === "open") return <>{children}</>;

  return (
    <div
      className="min-h-screen bg-[#0b0f17] flex items-center justify-center p-6"
      style={{ paddingTop: "env(safe-area-inset-top)", paddingBottom: "env(safe-area-inset-bottom)" }}
    >
      <form
        onSubmit={submit}
        className="w-full max-w-sm bg-[#101623] border border-white/5 rounded-xl p-6 space-y-4"
      >
        <div>
          <div className="text-lg font-semibold text-slate-100">Trdr</div>
          <div className="text-sm text-slate-500 mt-1">Enter the dashboard token to continue</div>
        </div>
        <input
          type="password"
          autoFocus
          value={token}
          onChange={(e) => {
            setToken(e.target.value);
            setError(false);
          }}
          placeholder="Dashboard token"
          className="w-full px-3 py-2.5 rounded-lg bg-black/30 border border-white/10 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-white/25"
        />
        {error && <div className="text-xs text-red-400">Invalid token</div>}
        <button
          type="submit"
          disabled={!token.trim()}
          className="w-full py-2.5 rounded-lg bg-white/10 hover:bg-white/15 text-sm font-medium text-slate-100 transition-colors disabled:opacity-40"
        >
          Unlock
        </button>
      </form>
    </div>
  );
};
