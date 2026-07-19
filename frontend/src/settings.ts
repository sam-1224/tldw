export interface Settings {
  mode: "free" | "byok";
  free_choice: string; // "auto" or "provider::model"
  provider: string;
  model_select: string;
  llm_key: string;
  supadata_key: string;
  model: string; // free-text override
  base_url: string;
  summary_lang: string;
}

const LS_KEY = "tldw.settings.v2";

export const DEFAULT_SETTINGS: Settings = {
  mode: "free",
  free_choice: "auto",
  provider: "gemini",
  model_select: "",
  llm_key: "",
  supadata_key: "",
  model: "",
  base_url: "",
  summary_lang: "English",
};

export function loadSettings(): Settings {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (raw) return { ...DEFAULT_SETTINGS, ...JSON.parse(raw) };
  } catch {}
  return { ...DEFAULT_SETTINGS };
}

export function saveSettings(s: Settings) {
  localStorage.setItem(LS_KEY, JSON.stringify(s));
}

const THEME_KEY = "tldw.theme";

export function initialTheme(): "light" | "dark" {
  const saved = localStorage.getItem(THEME_KEY);
  if (saved === "dark" || saved === "light") return saved;
  // dark-first: only an explicit OS light preference gets the light theme
  return window.matchMedia("(prefers-color-scheme: light)").matches
    ? "light"
    : "dark";
}

export function persistTheme(theme: "light" | "dark") {
  localStorage.setItem(THEME_KEY, theme);
}

export function fmt(sec: number): string {
  sec = Math.floor(sec || 0);
  const h = Math.floor(sec / 3600),
    m = Math.floor((sec % 3600) / 60),
    s = sec % 60;
  const mm = h ? String(m).padStart(2, "0") : String(m);
  return (h ? h + ":" : "") + mm + ":" + String(s).padStart(2, "0");
}

export function toSeconds(stamp: string | undefined): number {
  if (typeof stamp !== "string") return 0;
  const p = stamp.split(":").map(Number);
  if (p.some(isNaN)) return 0;
  return p.length === 3
    ? p[0] * 3600 + p[1] * 60 + p[2]
    : p.length === 2
      ? p[0] * 60 + p[1]
      : p[0];
}
