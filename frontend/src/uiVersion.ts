// UI version switch: "v2" (default) or "classic".
// Stored in localStorage so the choice survives reloads; switching reloads
// the page so the correct dashboard mounts from scratch.

export type UiVersion = "v2" | "classic";

const STORAGE_KEY = "ui_version";

export const getUiVersion = (): UiVersion => {
  try {
    return localStorage.getItem(STORAGE_KEY) === "classic" ? "classic" : "v2";
  } catch {
    return "v2";
  }
};

export const setUiVersion = (version: UiVersion): void => {
  try {
    localStorage.setItem(STORAGE_KEY, version);
  } catch {
    // localStorage unavailable - still reload so at least the default applies
  }
  window.location.reload();
};
