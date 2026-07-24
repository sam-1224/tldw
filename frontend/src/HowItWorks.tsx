import { useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";

/**
 * Landing-only "how to use it" section: three steps plus a self-playing
 * preview card that loops paste -> summarize -> jump so a first-time visitor
 * sees the whole flow without doing anything.
 */

const STEPS = [
  { n: "01", title: "Paste a link", body: "Drop any YouTube URL into the bar. No sign-up, no key — free models handle it." },
  { n: "02", title: "Get the gist", body: "A TL;DR, the key moments, takeaways, and a worth-watching score in seconds." },
  { n: "03", title: "Jump & ask", body: "Click any timestamp to jump to that second, or ask the video a question." },
];

const FRAMES = [
  { kind: "type", caption: "Paste a YouTube link" },
  { kind: "load", caption: "Reading the transcript…" },
  { kind: "result", caption: "Skim it. Jump anywhere." },
] as const;

const TYPED = "youtube.com/watch?v=…";

function DemoCard() {
  const reduced = useReducedMotion() ?? false;
  const [frame, setFrame] = useState(0);
  const [typed, setTyped] = useState(reduced ? TYPED : "");

  // advance frames on a loop
  useEffect(() => {
    if (reduced) return;
    const holds = [2600, 1800, 3200];
    const t = setTimeout(() => setFrame((f) => (f + 1) % FRAMES.length), holds[frame]);
    return () => clearTimeout(t);
  }, [frame, reduced]);

  // typewriter effect during the "type" frame
  useEffect(() => {
    if (reduced) return;
    if (FRAMES[frame].kind !== "type") return;
    setTyped("");
    let i = 0;
    const iv = setInterval(() => {
      i++;
      setTyped(TYPED.slice(0, i));
      if (i >= TYPED.length) clearInterval(iv);
    }, 70);
    return () => clearInterval(iv);
  }, [frame, reduced]);

  const f = FRAMES[frame];

  return (
    <div className="demo-card" aria-hidden="true">
      <div className="demo-bar">
        <span className="demo-dot" />
        <span className="demo-url">
          {f.kind === "type" ? typed || " " : TYPED}
          {f.kind === "type" && <i className="demo-caret" />}
        </span>
        <span className={"demo-go" + (f.kind === "load" ? " busy" : "")}>
          {f.kind === "load" ? "…" : "Summarize"}
        </span>
      </div>

      <div className="demo-track">
        <div className={"demo-fill" + (f.kind === "load" ? " run" : f.kind === "result" ? " done" : "")} />
        {f.kind === "result" &&
          [18, 41, 63, 86].map((l, i) => (
            <motion.span
              key={i}
              className="demo-tick"
              style={{ left: l + "%" }}
              initial={reduced ? { scale: 1 } : { scale: 0 }}
              animate={{ scale: 1 }}
              transition={reduced ? { duration: 0 } : { type: "spring", stiffness: 500, damping: 16, delay: i * 0.1 }}
            />
          ))}
      </div>

      <div className="demo-body">
        <AnimatePresence mode="wait">
          {f.kind === "result" ? (
            <motion.div
              key="res"
              className="demo-result"
              initial={reduced ? {} : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduced ? {} : { opacity: 0, y: -8 }}
              transition={{ duration: 0.3 }}
            >
              <span className="demo-tldr-label">TL;DW</span>
              <span className="demo-line w-90" />
              <span className="demo-line w-70" />
              <span className="demo-chips">
                <i /><i /><i />
              </span>
            </motion.div>
          ) : (
            <motion.div
              key="cap"
              className="demo-cap"
              initial={reduced ? {} : { opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={reduced ? {} : { opacity: 0 }}
              transition={{ duration: 0.3 }}
            >
              {f.caption}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <div className="demo-steps-dots">
        {FRAMES.map((_, i) => (
          <span key={i} className={"demo-sd" + (i === frame ? " on" : "")} />
        ))}
      </div>
    </div>
  );
}

export default function HowItWorks() {
  return (
    <section className="how">
      <p className="section-label how-eyebrow">How it works</p>
      <div className="how-grid">
        <div className="how-steps">
          {STEPS.map((s) => (
            <div className="how-step" key={s.n}>
              <span className="how-n">{s.n}</span>
              <div>
                <h3>{s.title}</h3>
                <p>{s.body}</p>
              </div>
            </div>
          ))}
        </div>
        <DemoCard />
      </div>
    </section>
  );
}
