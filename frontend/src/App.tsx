import { useEffect, useMemo, useRef, useState } from "react";
import { AppConfig, AskBody, SummarizeBody, SummarizeResult, ask as apiAsk, fetchConfig, summarize } from "./api";
import { AskFn } from "./QADock";
import { Settings, initialTheme, loadSettings, persistTheme, saveSettings } from "./settings";
import SettingsDrawer from "./SettingsDrawer";
import Results from "./Results";
import HowItWorks from "./HowItWorks";

const LOAD_MSGS = [
  "Fetching the transcript…",
  "Scrubbing past the intro…",
  "Fast-forwarding so you don't have to…",
  "Reading every word so you can read three…",
  "Finding the parts worth keeping…",
];

export default function App() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [settings, setSettings] = useState<Settings>(loadSettings);
  const [theme, setTheme] = useState<"light" | "dark">(initialTheme);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [saved, setSaved] = useState(false);
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadMsg, setLoadMsg] = useState(LOAD_MSGS[0]);
  const [error, setError] = useState<{ title: string; msg: string } | null>(null);
  const [result, setResult] = useState<SummarizeResult | null>(null);
  const resultsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    persistTheme(theme);
  }, [theme]);

  useEffect(() => {
    fetchConfig()
      .then((c) => {
        setConfig(c);
        if (!c.free_tier_available)
          setSettings((s) => (s.mode === "free" ? { ...s, mode: "byok" } : s));
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!loading) return;
    let i = 0;
    const iv = setInterval(() => {
      i = (i + 1) % LOAD_MSGS.length;
      setLoadMsg(LOAD_MSGS[i]);
    }, 2200);
    return () => clearInterval(iv);
  }, [loading]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setDrawerOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const provLabel = useMemo(() => {
    if (settings.mode === "free")
      return config?.free_tier_available
        ? "— free tier, no key needed"
        : "— add a key in settings";
    const p = config?.providers.find((x) => x.id === settings.provider);
    return settings.llm_key || settings.base_url
      ? `— summarizing with ${p?.label ?? settings.provider}`
      : "— add a key in settings";
  }, [settings, config]);

  // Fills provider/key/model/base_url from settings onto any request body.
  // Returns false (and shows an error + opens settings) when a key is missing.
  function applyProviderFields(
    body: { provider?: string; llm_key?: string | null; model?: string | null; base_url?: string | null },
  ): boolean {
    if (settings.mode === "free") {
      if (!config?.free_tier_available) {
        setError({
          title: "No model key yet",
          msg: "This server has no free tier configured. Open settings and add your own API key — free ones take ~2 minutes.",
        });
        setDrawerOpen(true);
        return false;
      }
      if (settings.free_choice && settings.free_choice !== "auto") {
        const [p, m] = settings.free_choice.split("::");
        body.provider = p;
        body.model = m;
      }
      return true;
    }
    const pcfg = config?.providers.find((x) => x.id === settings.provider);
    const needsKey = !(pcfg && pcfg.key_optional);
    if (needsKey && !settings.llm_key) {
      setError({
        title: "No model key yet",
        msg: "Open settings (top right) and add an API key for your chosen provider.",
      });
      setDrawerOpen(true);
      return false;
    }
    body.provider = settings.provider;
    body.llm_key = settings.llm_key || null;
    body.model = settings.model || settings.model_select || null;
    if (pcfg?.needs_base_url) {
      if (!settings.base_url) {
        setError({
          title: "No base URL",
          msg: "The custom provider needs the base URL of your local server, e.g. http://localhost:11434/v1.",
        });
        setDrawerOpen(true);
        return false;
      }
      body.base_url = settings.base_url;
    }
    return true;
  }

  // Passed to the Q&A dock. Throws on a missing key so the dock shows it inline.
  const askQuestion: AskFn = async (question, history) => {
    if (!result) throw new Error("Summarize a video first.");
    const body: AskBody = {
      question,
      segments: result.segments,
      history,
      summary_lang: settings.summary_lang || null,
    };
    if (!applyProviderFields(body)) throw new Error("Add an API key in settings first.");
    return apiAsk(body);
  };

  async function run() {
    setError(null);
    setResult(null);
    const trimmed = url.trim();
    if (!trimmed) {
      setError({ title: "Need a link", msg: "Paste a YouTube URL to get started." });
      return;
    }

    const body: SummarizeBody = {
      url: trimmed,
      supadata_key: settings.supadata_key || null,
      summary_lang: settings.summary_lang || null,
    };
    if (!applyProviderFields(body)) return;

    setLoading(true);
    setLoadMsg(LOAD_MSGS[0]);
    try {
      const d = await summarize(body);
      setResult(d);
      setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 60);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Unknown error.";
      setError({
        title: msg.includes("respond") ? "Connection problem" : "Couldn't summarize that",
        msg,
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="wrap">
      <div className="aurora" aria-hidden="true"><div className="blob" /></div>
      <header className="glass">
        <div className="brand">
          TL<span className="semi">;</span>DW <small>too long · didn't watch</small>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button
            className="icon-btn"
            aria-label="Toggle dark mode"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          >
            {theme === "dark" ? (
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="5" /><line x1="12" y1="1" x2="12" y2="3" /><line x1="12" y1="21" x2="12" y2="23" /><line x1="4.22" y1="4.22" x2="5.64" y2="5.64" /><line x1="18.36" y1="18.36" x2="19.78" y2="19.78" /><line x1="1" y1="12" x2="3" y2="12" /><line x1="21" y1="12" x2="23" y2="12" /><line x1="4.22" y1="19.78" x2="5.64" y2="18.36" /><line x1="18.36" y1="5.64" x2="19.78" y2="4.22" /></svg>
            ) : (
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" /></svg>
            )}
          </button>
          <button className="icon-btn" aria-label="Open settings" onClick={() => setDrawerOpen(true)}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" /></svg>
          </button>
        </div>
      </header>

      <section className={"hero" + (result ? " compact" : "")}>
        <div className="eyebrow">paste a link · skip the watch</div>
        <h1>
          Watch less.<br />
          <span className="mark"><span className="shiny">Know</span> more.</span>
        </h1>
        <p className="sub">
          Drop a YouTube URL. Get the gist, the key moments, and timestamps you can jump to.
        </p>

        <div className="console">
          <div className="console-row">
            <span className="play-dot" aria-hidden="true">
              <span className="ripple" />
              <span className="ripple ripple-2" />
              <svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z" /></svg>
            </span>
            <input
              id="url"
              type="url"
              placeholder="https://youtube.com/watch?v=…"
              autoComplete="off"
              spellCheck={false}
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && run()}
            />
            <button className="go" onClick={run} disabled={loading}>Summarize</button>
          </div>
          <div className="timeline">
            <div className={"fill" + (loading ? " loading" : "")} style={loading ? undefined : { width: "0%" }} />
          </div>
          <div className="meta-line">
            <span>free transcript · whisper fallback</span>
            <span>{provLabel}</span>
          </div>
        </div>

        <p className="hint">
          No account, no key needed — runs on <b>free models</b>. Add your own
          API key in settings for premium models; it stays in <b>your browser</b>.
        </p>
      </section>

      {!result && !loading && <HowItWorks />}

      {loading && (
        <div className="loading on">
          <div className="scan" />
          <div id="loadMsg" aria-live="polite">{loadMsg}</div>
        </div>
      )}

      {error && (
        <div className="error on">
          <h4>{error.title}</h4>
          <p>{error.msg}</p>
        </div>
      )}

      <div ref={resultsRef}>{result && <Results d={result} askFn={askQuestion} />}</div>

      <footer>
        Open source · BYOK ·{" "}
        <a href="https://github.com" target="_blank" rel="noopener">fork it on GitHub</a>
      </footer>

      <SettingsDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        config={config}
        settings={settings}
        onChange={setSettings}
        onSave={() => {
          saveSettings(settings);
          setSaved(true);
          setTimeout(() => setSaved(false), 1600);
        }}
        saved={saved}
      />
    </div>
  );
}
