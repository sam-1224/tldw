import { AppConfig, ProviderInfo } from "./api";
import { Settings } from "./settings";

interface Props {
  open: boolean;
  onClose: () => void;
  config: AppConfig | null;
  settings: Settings;
  onChange: (s: Settings) => void;
  onSave: () => void;
  saved: boolean;
}

export default function SettingsDrawer({
  open, onClose, config, settings, onChange, onSave, saved,
}: Props) {
  const providers: ProviderInfo[] = config?.providers ?? [];
  const current = providers.find((p) => p.id === settings.provider);
  const set = (patch: Partial<Settings>) => onChange({ ...settings, ...patch });

  return (
    <>
      <div className={"scrim" + (open ? " on" : "")} onClick={onClose} />
      <aside className={"drawer" + (open ? " on" : "")} aria-label="Settings">
        <h3>Settings</h3>
        <p className="note">
          Free mode needs no key. Bring your own key for premium models — it
          never leaves your browser except to the provider you pick.
        </p>

        <div className="mode-switch" role="tablist" aria-label="Key mode">
          <button
            className={"mode-btn" + (settings.mode === "free" ? " on" : "")}
            role="tab"
            onClick={() => set({ mode: "free" })}
          >
            Free
          </button>
          <button
            className={"mode-btn" + (settings.mode === "byok" ? " on" : "")}
            role="tab"
            onClick={() => set({ mode: "byok" })}
          >
            Your API key
          </button>
        </div>

        {settings.mode === "free" && (
          <div>
            <div className="free-banner">
              {config?.free_tier_available
                ? "Running on this server's free tier — no key needed."
                : "This server has no free-tier key configured — add your own key in the other tab."}
            </div>
            <div className="field">
              <label htmlFor="freeModel">Free model</label>
              <select
                id="freeModel"
                value={settings.free_choice}
                onChange={(e) => set({ free_choice: e.target.value })}
              >
                <option value="auto">Auto — best free model (with failover)</option>
                {(config?.free_chain ?? []).flatMap((pid) => {
                  const p = providers.find((x) => x.id === pid);
                  return (p?.models ?? []).map((m) => (
                    <option key={pid + m} value={`${pid}::${m}`}>
                      {p!.label} — {m}
                    </option>
                  ));
                })}
              </select>
              <div className="help">
                Auto picks the best free model and fails over if a rate limit is hit.
              </div>
            </div>
          </div>
        )}

        {settings.mode === "byok" && (
          <div>
            <div className="field">
              <label htmlFor="provider">Provider</label>
              <select
                id="provider"
                value={settings.provider}
                onChange={(e) => {
                  const p = providers.find((x) => x.id === e.target.value);
                  set({
                    provider: e.target.value,
                    model_select: p?.default_model ?? "",
                  });
                }}
              >
                {providers.map((p) => (
                  <option key={p.id} value={p.id}>{p.label}</option>
                ))}
              </select>
            </div>

            {current?.needs_base_url && (
              <div className="field">
                <label htmlFor="baseUrl">Base URL</label>
                <input
                  id="baseUrl"
                  type="text"
                  placeholder="http://localhost:11434/v1"
                  autoComplete="off"
                  value={settings.base_url}
                  onChange={(e) => set({ base_url: e.target.value })}
                />
                <div className="help">Any OpenAI-compatible server: Ollama, LM Studio, vLLM…</div>
              </div>
            )}

            <div className="field">
              <label htmlFor="modelSelect">Model</label>
              <select
                id="modelSelect"
                value={settings.model_select}
                onChange={(e) => set({ model_select: e.target.value })}
              >
                {(current?.models.length ? current.models : [""]).map((m, i) => (
                  <option key={m || "none"} value={m}>
                    {m ? m + (i === 0 ? " (default)" : "") : "type a model id below"}
                  </option>
                ))}
              </select>
            </div>

            <div className="field">
              <label htmlFor="model">Custom model id — optional</label>
              <input
                id="model"
                type="text"
                placeholder="overrides the dropdown when filled"
                autoComplete="off"
                value={settings.model}
                onChange={(e) => set({ model: e.target.value })}
              />
            </div>

            <div className="field">
              <label htmlFor="llmKey">
                API key{current?.key_optional ? " — optional for local servers" : ""}
              </label>
              <input
                id="llmKey"
                type="password"
                placeholder="sk-… / your provider key"
                autoComplete="off"
                value={settings.llm_key}
                onChange={(e) => set({ llm_key: e.target.value })}
              />
              <div className="help">
                Free keys in ~2 min:{" "}
                <a href="https://aistudio.google.com" target="_blank" rel="noopener">Gemini</a>,{" "}
                <a href="https://console.groq.com" target="_blank" rel="noopener">Groq</a>,{" "}
                <a href="https://openrouter.ai" target="_blank" rel="noopener">OpenRouter</a>.
              </div>
            </div>
          </div>
        )}

        <div className="field">
          <label htmlFor="summaryLang">Summary language</label>
          <select
            id="summaryLang"
            value={settings.summary_lang}
            onChange={(e) => set({ summary_lang: e.target.value })}
          >
            {(config?.summary_languages ?? ["English"]).map((l) => (
              <option key={l} value={l}>{l}</option>
            ))}
          </select>
          <div className="help">
            Summaries are written in this language, whatever language the video is in.
          </div>
        </div>

        <div className="field">
          <label htmlFor="supaKey">Supadata key — optional</label>
          <input
            id="supaKey"
            type="password"
            placeholder="for videos without captions"
            autoComplete="off"
            value={settings.supadata_key}
            onChange={(e) => set({ supadata_key: e.target.value })}
          />
          <div className="help">
            Only used as a fallback when a video has no captions.{" "}
            <a href="https://supadata.ai" target="_blank" rel="noopener">Free 100/mo →</a>
          </div>
        </div>

        <button className="save" onClick={onSave}>Save to this browser</button>
        <div className={"saved-flag" + (saved ? " on" : "")}>Saved ✓</div>

        <div className="privacy">
          Keys live in <b>localStorage</b> on this device only. Clear them any
          time by emptying the fields and saving. This tool never stores them
          server-side.
        </div>
      </aside>
    </>
  );
}
