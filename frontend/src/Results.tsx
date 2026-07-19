import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { SummarizeResult } from "./api";
import { fmt, toSeconds } from "./settings";
import QADock, { AskFn } from "./QADock";

const CHUNK = 200;

function Transcript({ d }: { d: SummarizeResult }) {
  const [count, setCount] = useState(CHUNK);
  const sentinel = useRef<HTMLDivElement>(null);
  const body = useRef<HTMLDivElement>(null);
  const segs = d.segments ?? [];

  useEffect(() => setCount(CHUNK), [d]);

  useEffect(() => {
    const el = sentinel.current;
    if (!el || count >= segs.length) return;
    const obs = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) setCount((c) => Math.min(c + CHUNK, segs.length));
      },
      { root: body.current },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [count, segs.length]);

  const watchUrl = (s: number) =>
    `https://www.youtube.com/watch?v=${d.video_id}&t=${Math.floor(s)}s`;

  return (
    <details className="transcript">
      <summary>Full transcript</summary>
      <div className="transcript-body" ref={body}>
        {d.summary.truncated && (
          <div className="tline">
            <span className="stamp note">note</span>
            <span>
              Transcript was long, so it was trimmed before summarizing to keep
              cost down. Full transcript below.
            </span>
          </div>
        )}
        {segs.length === 0 && (
          <div className="tline"><span>Transcript unavailable.</span></div>
        )}
        {segs.slice(0, count).map((seg, i) => (
          <div className="tline" key={i}>
            <a className="stamp" href={watchUrl(seg.start)} target="_blank" rel="noopener">
              {fmt(seg.start)}
            </a>
            <span>{seg.text}</span>
          </div>
        ))}
        <div ref={sentinel} />
      </div>
    </details>
  );
}

function Tick({ href, left, title, delay, reduced }: {
  href: string; left: string; title: string; delay: number; reduced: boolean;
}) {
  return (
    <motion.a
      className="tick show"
      href={href}
      target="_blank"
      rel="noopener"
      style={{ left }}
      data-tip={title}
      aria-label={title}
      initial={reduced ? { scale: 1 } : { scale: 0 }}
      animate={{ scale: 1 }}
      whileHover={{ scale: 1.35 }}
      transition={
        reduced
          ? { duration: 0 }
          : { type: "spring", stiffness: 500, damping: 18, delay }
      }
    />
  );
}

export default function Results({ d, askFn }: { d: SummarizeResult; askFn: AskFn }) {
  const s = d.summary;
  const dur = d.duration_seconds || 0;
  const reduced = useReducedMotion() ?? false;
  const [flashSec, setFlashSec] = useState<number | null>(null);
  const watchUrl = (sec: number) =>
    `https://www.youtube.com/watch?v=${d.video_id}&t=${Math.floor(sec)}s`;

  // a citation click/hover drops a temporary white tick on the scrubber
  function flashCitation(sec: number) {
    setFlashSec(sec);
    window.setTimeout(() => setFlashSec((cur) => (cur === sec ? null : cur)), 2000);
  }

  const langTag =
    d.transcript_language && d.transcript_language.toLowerCase().slice(0, 2) !== "en"
      ? ` · ${d.transcript_language.toUpperCase()} → EN`
      : "";

  // one motion config for every bento card, staggered by index
  let cardIndex = 0;
  const card = (area: string, extra = "") => {
    const i = cardIndex++;
    return {
      className: `bento-card area-${area} ${extra}`.trim(),
      initial: reduced ? { opacity: 1, y: 0 } : { opacity: 0, y: 8 },
      animate: { opacity: 1, y: 0 },
      transition: reduced
        ? { duration: 0.12 }
        : { type: "spring" as const, stiffness: 260, damping: 24, delay: i * 0.06 },
    };
  };

  return (
    <section className="results on">
      <div className="vid">
        <img src={d.thumbnail || ""} alt="" />
        <div>
          <div className="vt">{d.title || "Untitled video"}</div>
          <div className="va">
            {[d.author, dur ? fmt(dur) : null].filter(Boolean).join(" · ")}
          </div>
          <span className="badge">
            {(d.transcript_source === "supadata" ? "AI transcript (Supadata)" : "captions") + langTag}
          </span>
        </div>
      </div>

      <p className="section-label">The timeline · tap a marker to jump</p>
      <div className="timeline" style={{ marginBottom: 30 }}>
        {dur > 0 &&
          (s.key_points ?? []).map((p, idx) => {
            const sec = toSeconds(p.timestamp);
            return (
              <Tick
                key={idx}
                href={watchUrl(sec)}
                left={Math.min(98, Math.max(1, (sec / dur) * 100)) + "%"}
                title={`${p.timestamp} — ${p.point || ""}`}
                delay={0.12 + idx * 0.09}
                reduced={reduced}
              />
            );
          })}
        {dur > 0 && flashSec !== null && (
          <span
            className="tick flash show"
            style={{ left: Math.min(98, Math.max(1, (flashSec / dur) * 100)) + "%" }}
            aria-hidden="true"
          />
        )}
      </div>

      <div className="bento">
        <motion.div {...card("tldr", "tldr")}>
          <p className="section-label">TL;DW</p>
          <p>{s.tldr || "No summary returned."}</p>
        </motion.div>

        <motion.div {...card("moments")}>
          <p className="section-label">Key moments</p>
          <div className="points">
            {(s.key_points ?? []).map((p, i) => (
              <motion.div
                className="point"
                key={i}
                initial={reduced ? { opacity: 1, x: 0 } : { opacity: 0, x: 14 }}
                animate={{ opacity: 1, x: 0 }}
                transition={
                  reduced
                    ? { duration: 0.1 }
                    : { type: "spring", stiffness: 300, damping: 26, delay: 0.25 + i * 0.07 }
                }
              >
                <a className="stamp" href={watchUrl(toSeconds(p.timestamp))} target="_blank" rel="noopener">
                  {p.timestamp || "—"}
                </a>
                <p>
                  {p.point || ""}
                  {p.detail && <span className="pd">{p.detail}</span>}
                </p>
              </motion.div>
            ))}
          </div>
        </motion.div>

        {!!s.breakdown?.length && (
          <motion.div {...card("breakdown")}>
            <p className="section-label">The breakdown</p>
            <div className="breakdown">
              {s.breakdown.map((t, i) => <p key={i}>{t}</p>)}
            </div>
          </motion.div>
        )}

        {!!s.takeaways?.length && (
          <motion.div {...card("takeaways")}>
            <p className="section-label">Takeaways</p>
            <ul className="takeaways">
              {s.takeaways.map((t, i) => <li key={i}>{t}</li>)}
            </ul>
          </motion.div>
        )}

        {s.worth_watching && typeof s.worth_watching.score === "number" && (
          <motion.div {...card("worth")}>
            <div className="worth-inner">
              <span className="worth-score">{s.worth_watching.score}/10</span>
              <div>
                <p className="section-label" style={{ margin: "0 0 2px" }}>Worth watching?</p>
                <p className="worth-reason">{s.worth_watching.reason || ""}</p>
              </div>
            </div>
            {!!s.topics?.length && (
              <div className="topics" style={{ marginTop: 14, marginBottom: 0 }}>
                {s.topics.map((t, i) => <span className="topic" key={i}>{t}</span>)}
              </div>
            )}
          </motion.div>
        )}

        <motion.div {...card("qa")}>
          <QADock d={d} askFn={askFn} onCite={flashCitation} />
        </motion.div>

        <motion.div {...card("transcript")}>
          <Transcript d={d} />
        </motion.div>
      </div>
    </section>
  );
}
