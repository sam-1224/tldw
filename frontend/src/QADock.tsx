import { useState } from "react";
import { motion } from "motion/react";
import { AskAnswer, Citation, SummarizeResult } from "./api";

export interface AskFn {
  (question: string, history: { role: "user" | "assistant"; content: string }[]): Promise<AskAnswer>;
}

interface Turn {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  error?: boolean;
}

interface Props {
  d: SummarizeResult;
  askFn: AskFn;
  onCite: (seconds: number) => void;
}

export default function QADock({ d, askFn, onCite }: Props) {
  const [thread, setThread] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  // three suggested questions seeded from the summary's key points
  const suggestions = (d.summary.key_points ?? [])
    .slice(0, 3)
    .map((p) => `What did they say about ${p.point.replace(/[.?!]$/, "").toLowerCase()}?`);

  const watchUrl = (sec: number) =>
    `https://www.youtube.com/watch?v=${d.video_id}&t=${Math.floor(sec)}s`;

  async function submit(q: string) {
    const question = q.trim();
    if (!question || busy) return;
    setInput("");
    const history = thread.map((t) => ({ role: t.role, content: t.content }));
    setThread((t) => [...t, { role: "user", content: question }]);
    setBusy(true);
    try {
      const res = await askFn(question, history);
      setThread((t) => [
        ...t,
        { role: "assistant", content: res.answer, citations: res.citations },
      ]);
    } catch (e) {
      setThread((t) => [
        ...t,
        {
          role: "assistant",
          content: e instanceof Error ? e.message : "Something went wrong.",
          error: true,
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="qa">
      <p className="section-label">Ask the video</p>

      <div className="qa-thread">
        {thread.length === 0 && !busy && (
          <div className="qa-empty">
            <p>Ask anything — answers come straight from this video's transcript, with timestamps you can jump to.</p>
            <div className="qa-chips">
              {suggestions.map((s, i) => (
                <button key={i} className="qa-chip" onClick={() => submit(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {thread.map((t, i) => (
          <motion.div
            key={i}
            className={`qa-msg qa-${t.role}` + (t.error ? " qa-error" : "")}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2 }}
          >
            <span className="qa-bubble">{t.content}</span>
            {!!t.citations?.length && (
              <div className="qa-cites">
                {t.citations.map((c, j) => {
                  const seg = d.segments[c.segment_index];
                  const sec = seg ? seg.start : 0;
                  return (
                    <a
                      key={j}
                      className="qa-cite"
                      href={watchUrl(sec)}
                      target="_blank"
                      rel="noopener"
                      onMouseEnter={() => onCite(sec)}
                      onFocus={() => onCite(sec)}
                    >
                      {c.timestamp}
                    </a>
                  );
                })}
              </div>
            )}
          </motion.div>
        ))}

        {busy && (
          <div className="qa-msg qa-assistant">
            <span className="qa-bubble qa-typing"><i /><i /><i /></span>
          </div>
        )}
      </div>

      <form
        className="qa-input"
        onSubmit={(e) => {
          e.preventDefault();
          submit(input);
        }}
      >
        <input
          type="text"
          placeholder="Ask a question about this video…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={busy}
          aria-label="Ask a question about this video"
        />
        <button type="submit" disabled={busy || !input.trim()}>Ask</button>
      </form>
    </div>
  );
}
