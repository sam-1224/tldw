import { useEffect, useRef, useState } from "react";
import { SummarizeResult } from "./api";
import { fmt, toSeconds } from "./settings";

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

export default function Results({ d }: { d: SummarizeResult }) {
  const s = d.summary;
  const dur = d.duration_seconds || 0;
  const watchUrl = (sec: number) =>
    `https://www.youtube.com/watch?v=${d.video_id}&t=${Math.floor(sec)}s`;
  const [ticksShown, setTicksShown] = useState(false);
  useEffect(() => {
    setTicksShown(false);
    const t = setTimeout(() => setTicksShown(true), 120);
    return () => clearTimeout(t);
  }, [d]);

  const langTag =
    d.transcript_language && d.transcript_language.toLowerCase().slice(0, 2) !== "en"
      ? ` · ${d.transcript_language.toUpperCase()} → EN`
      : "";

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
        {(s.key_points ?? []).map((p, idx) => {
          const sec = toSeconds(p.timestamp);
          if (dur <= 0) return null;
          return (
            <a
              key={idx}
              className={"tick" + (ticksShown ? " show" : "")}
              href={watchUrl(sec)}
              target="_blank"
              rel="noopener"
              style={{
                left: Math.min(98, Math.max(1, (sec / dur) * 100)) + "%",
                transitionDelay: `${idx * 90}ms`,
              }}
              title={`${p.timestamp} — ${p.point || ""}`}
            />
          );
        })}
      </div>

      <div className="tldr">
        <p className="section-label">TL;DW</p>
        <p>{s.tldr || "No summary returned."}</p>
      </div>

      {!!s.breakdown?.length && (
        <div>
          <p className="section-label">The breakdown</p>
          <div className="breakdown">
            {s.breakdown.map((t, i) => <p key={i}>{t}</p>)}
          </div>
        </div>
      )}

      <p className="section-label">Key moments</p>
      <div className="points">
        {(s.key_points ?? []).map((p, i) => (
          <div className="point" key={i}>
            <a className="stamp" href={watchUrl(toSeconds(p.timestamp))} target="_blank" rel="noopener">
              {p.timestamp || "—"}
            </a>
            <p>
              {p.point || ""}
              {p.detail && <span className="pd">{p.detail}</span>}
            </p>
          </div>
        ))}
      </div>

      {!!s.takeaways?.length && (
        <div>
          <p className="section-label">Takeaways</p>
          <ul className="takeaways">
            {s.takeaways.map((t, i) => <li key={i}>{t}</li>)}
          </ul>
        </div>
      )}

      {s.worth_watching && typeof s.worth_watching.score === "number" && (
        <div className="worth">
          <span className="worth-score">{s.worth_watching.score}/10</span>
          <div>
            <p className="section-label" style={{ margin: "0 0 2px" }}>Worth watching?</p>
            <p className="worth-reason">{s.worth_watching.reason || ""}</p>
          </div>
        </div>
      )}

      {!!s.topics?.length && (
        <div className="topics">
          {s.topics.map((t, i) => <span className="topic" key={i}>{t}</span>)}
        </div>
      )}

      <Transcript d={d} />
    </section>
  );
}
