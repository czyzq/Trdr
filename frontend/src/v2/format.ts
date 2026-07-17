// Shared formatting helpers for Dashboard v2.

export const fmtUsd = (v: number | null | undefined, withSign = false): string => {
  if (v === null || v === undefined || Number.isNaN(v)) return "–";
  const sign = withSign && v > 0 ? "+" : "";
  return `${sign}$${v.toFixed(2)}`;
};

export const fmtPrice = (price: number | null | undefined): string => {
  if (price === null || price === undefined || Number.isNaN(price)) return "–";
  if (price > 10000) return price.toFixed(0);
  if (price > 100) return price.toFixed(2);
  return price.toFixed(4);
};

export const fmtDateTime = (dateStr: string | null | undefined): string => {
  if (!dateStr) return "–";
  const date = new Date(dateStr.replace("Z", "+00:00"));
  if (Number.isNaN(date.getTime())) return "–";
  return date.toLocaleString("en-GB", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Warsaw",
  });
};

export const fmtTime = (dateStr: string | null | undefined): string => {
  if (!dateStr) return "–";
  const date = new Date(dateStr.replace("Z", "+00:00"));
  if (Number.isNaN(date.getTime())) return "–";
  return date.toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    timeZone: "Europe/Warsaw",
  });
};

export const pnlClass = (v: number | null | undefined): string =>
  (v ?? 0) >= 0 ? "text-green-400" : "text-red-400";
