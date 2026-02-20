// Theme definitions for CFD Trading Bot

export type ThemeName = "original" | "black" | "daylight";

export interface Theme {
  name: ThemeName;
  displayName: string;
  colors: {
    // Backgrounds
    bgPrimary: string;
    bgSecondary: string;
    bgTertiary: string;
    
    // Borders
    border: string;
    borderLight: string;
    
    // Text
    textPrimary: string;
    textSecondary: string;
    textMuted: string;
    
    // Accents
    accent: string;
    success: string;
    danger: string;
    warning: string;
    
    // Chart specific
    chartBg: string;
    gridLine: string;
    chartText: string;
    chartCandleUp: string;
    chartCandleDown: string;
  };
}

export const themes: Record<ThemeName, Theme> = {
  original: {
    name: "original",
    displayName: "Original (Purple)",
    colors: {
      bgPrimary: "#0b0f1a",
      bgSecondary: "#0d1220",
      bgTertiary: "#1a1f35",
      border: "#1a1f35",
      borderLight: "#2a3349",
      textPrimary: "#e2e8f0",
      textSecondary: "#9ca3af",
      textMuted: "#64748b",
      accent: "#3b82f6",
      success: "#22c55e",
      danger: "#ef4444",
      warning: "#f59e0b",
      chartBg: "#0d1220",
      gridLine: "#1a1f35",
      chartText: "#374151",
      chartCandleUp: "#22c55e",
      chartCandleDown: "#ef4444",
    },
  },
  black: {
    name: "black",
    displayName: "Black & Grey",
    colors: {
      bgPrimary: "#000000",
      bgSecondary: "#0a0a0a",
      bgTertiary: "#171717",
      border: "#262626",
      borderLight: "#404040",
      textPrimary: "#f5f5f5",
      textSecondary: "#a3a3a3",
      textMuted: "#737373",
      accent: "#ffffff",
      success: "#4ade80",
      danger: "#f87171",
      warning: "#fbbf24",
      chartBg: "#000000",
      gridLine: "#171717",
      chartText: "#525252",
      chartCandleUp: "#4ade80",
      chartCandleDown: "#f87171",
    },
  },
  daylight: {
    name: "daylight",
    displayName: "Daylight",
    colors: {
      bgPrimary: "#f8fafc",
      bgSecondary: "#ffffff",
      bgTertiary: "#f1f5f9",
      border: "#e2e8f0",
      borderLight: "#cbd5e1",
      textPrimary: "#0f172a",
      textSecondary: "#475569",
      textMuted: "#94a3b8",
      accent: "#2563eb",
      success: "#16a34a",
      danger: "#dc2626",
      warning: "#d97706",
      chartBg: "#ffffff",
      gridLine: "#e2e8f0",
      chartText: "#6b7280",
      chartCandleUp: "#16a34a",
      chartCandleDown: "#dc2626",
    },
  },
};

// Get stored theme or default to original
export function getStoredTheme(): ThemeName {
  if (typeof window === "undefined") return "original";
  const stored = localStorage.getItem("theme");
  if (stored && themes[stored as ThemeName]) return stored as ThemeName;
  return "original";
}

// Store theme preference
export function setStoredTheme(theme: ThemeName): void {
  if (typeof window === "undefined") return;
  localStorage.setItem("theme", theme);
}

// Get current theme colors
export function getThemeColors(): Theme["colors"] {
  return themes[getStoredTheme()].colors;
}
