"use client";
import { useEffect, useMemo, useState } from "react";
import { analyze } from "../lib/api";

const STAGES = ["Informal idea", "Query expansion", "Multi-source search", "Embeddings", "Knowledge graph", "GraphRAG", "Blindspot report"];
const COLS = [["papers", "Papers"], ["patents", "Patents"], ["code", "Code"]];
const EXAMPLES = ["An app that checks if my project idea already exists online", "A chatbot that answers college attendance questions using our PDFs", "Drone that detects crop disease from photos and tells farmers what to spray"];
const TABS = ["Overview", "Blindspot Matrix", "Sources", "Benchmark"];
const avg = (c) => (c.papers + c.patents + c.code) / 3;
const heat = (v) => `hsl(${Math.round(150 - v * 150)} 80% 55%)`;

function Ring({ value }) {
  const r = 58, c = 2 * Math.PI * r;
  return (
    <svg width="160" height="160" viewBox="0 0 160 160">
      <defs><linearGradient id="rg"><stop offset="0" stopColor="#7c5cff" /><stop offset="1" stopColor="#22d3ee" /></linearGradient></defs>
      <circle cx="80" cy="80" r={r} className="ring-bg" />
      <circle cx="80" cy="80" r={r} className="ring-fg" stroke="url(#rg)" strokeDasharray={c} strokeDashoffset={c * (1 - value / 100)} />
      <text x="80" y="82" textAnchor="middle" className="ring-t">{value}</text>
      <text x="80" y="102" textAnchor="middle" className="ring-s">ORIGINALITY</text>
    </svg>
  );
}

function Graph({ data, sel, setSel }) {
  const { nodes, edges } = useMemo(() => {
    const cx = 320, cy = 210, n = data.concepts.length, ns = [], es = [];
    const pos = {};
    data.concepts.forEach((c, i) => {
      const a = (i / n) * 2 * Math.PI - Math.PI / 2;
      pos[c.name] = { x: cx + 115 * Math.cos(a), y: cy + 115 * Math.sin(a), a };
      ns.push({ id: c.name, type: "concept", item: c, ...pos[c.name], r: 18 + avg(c) * 10, color: heat(avg(c)) });
      es.push({ x1: cx, y1: cy, x2: pos[c.name].x, y2: pos[c.name].y });
    });
    data.overlaps.forEach((o, i) => {
      const links = o.concepts.filter((k) => pos[k]);
      const a = links.length ? links.reduce((s, k) => s + pos[k].a, 0) / links.length + (i % 2 ? 0.18 : -0.18) : (i / data.overlaps.length) * 6.28;
      const p = { x: cx + 190 * Math.cos(a), y: cy + 185 * Math.sin(a) };
      ns.push({ id: "s" + i, type: "source", item: o, ...p, r: 9, color: { arxiv: "#fb923c", patent: "#facc15", github: "#4ade80" }[o.source] || "#aaa" });
      links.forEach((k) => es.push({ x1: pos[k].x, y1: pos[k].y, x2: p.x, y2: p.y, dim: true }));
    });
    return { nodes: ns, edges: es };
  }, [data]);
  return (
    <svg viewBox="0 0 640 420" className="graph">
      {edges.map((e, i) => <line key={i} {...e} className={e.dim ? "edge dim" : "edge"} />)}
      <circle cx="320" cy="210" r="26" className="core" />
      <text x="320" y="214" textAnchor="middle" className="gt">YOUR IDEA</text>
      {nodes.map((n) => (
        <g key={n.id} className={"node" + (sel?.id === n.id ? " act" : "")} onClick={() => setSel(n)}>
          <circle cx={n.x} cy={n.y} r={n.r} fill={n.color} fillOpacity=".25" stroke={n.color} strokeWidth="2" />
          {n.type === "concept" && <text x={n.x} y={n.y + n.r + 14} textAnchor="middle" className="gl">{n.id}</text>}
        </g>))}
    </svg>
  );
}

function Detail({ sel }) {
  if (!sel) return <p className="muted">Click any node in the graph to inspect it.</p>;
  if (sel.type === "concept") {
    const c = sel.item, a = avg(c);
    return (<div><span className="tag" style={{ color: heat(a) }}>{a > 0.6 ? "Heavily covered" : a > 0.3 ? "Partly explored" : "Uncharted"}</span>
      <h4>{c.name}</h4><p className="muted">Novelty {Math.round((1 - a) * 100)}%</p>
      {COLS.map(([k, l]) => <Bar key={k} label={l} v={c[k]} />)}</div>);
  }
  const o = sel.item;
  return (<div><span className={`tag ${o.source}`}>{o.source}</span><h4>{o.title}</h4>
    <p className="muted">Similarity {Math.round(o.similarity * 100)}%</p>
    <a className="btn2" href={o.url} target="_blank" rel="noreferrer">Open source ↗</a></div>);
}

const Bar = ({ label, v, color }) => (
  <div className="bar"><span>{label}</span><div><i style={{ width: `${v * 100}%`, background: color || heat(v) }} /></div><b>{Math.round(v * 100)}%</b></div>
);

export default function Home() {
  const [idea, setIdea] = useState("");
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState(0);
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [tab, setTab] = useState(0);
  const [sel, setSel] = useState(null);
  const [filter, setFilter] = useState("all");

  useEffect(() => {
    const m = (e) => { document.documentElement.style.setProperty("--mx", e.clientX + "px"); document.documentElement.style.setProperty("--my", e.clientY + "px"); };
    window.addEventListener("mousemove", m); return () => window.removeEventListener("mousemove", m);
  }, []);

  async function run() {
    if (idea.trim().length < 15) return setErr("Describe your idea in a bit more detail (15+ characters).");
    setErr(""); setData(null); setLoading(true); setStep(0); setSel(null); setTab(0);
    const t = setInterval(() => setStep((s) => Math.min(s + 1, STAGES.length - 1)), 480);
    try { setData(await analyze(idea)); setTimeout(() => document.getElementById("results")?.scrollIntoView({ behavior: "smooth" }), 100); }
    catch (e) { setErr(e.message || "Something went wrong."); }
    finally { clearInterval(t); setLoading(false); }
  }
  const download = () => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([JSON.stringify({ idea, ...data }, null, 2)], { type: "application/json" }));
    a.download = "cognigap-report.json"; a.click();
  };
  const colAvg = (k) => data ? data.concepts.reduce((s, c) => s + c[k], 0) / Math.max(1, data.concepts.length) : 0;
  const verdict = data ? (data.score >= 70 ? "Largely novel" : data.score >= 40 ? "Partially explored" : "Heavily covered") : "";

  return (
    <>
      <div className="spot" /><div className="gridbg" />
      <nav className="nav">
        <b className="logo"><span className="dot" />CogniGap</b>
        <div className="links"><a href="#analyze">Analyze</a><a href="#how">How it works</a><a href="#stack">Tech</a></div>
      </nav>

      <header className="hero">
        <span className="pill"><i className="live" />GraphRAG · Knowledge Graphs · Prior-art AI</span>
        <h1>Is your idea <em>actually</em> new?</h1>
        <p>Describe your project in everyday language. CogniGap translates it into research vocabulary, scans papers, patents and open-source code, then maps exactly where you overlap — and where you stand alone.</p>
        <div className="stats"><div><b>3</b>sources scanned</div><div><b>Multi-hop</b>graph reasoning</div><div><b>Live</b>Blindspot Matrix</div></div>
      </header>

      <section id="analyze" className="card input">
        <textarea value={idea} onChange={(e) => setIdea(e.target.value)} rows={5} placeholder="Describe your project idea in plain English…" />
        <div className="ex">{EXAMPLES.map((x) => <button key={x} className="chipbtn" onClick={() => setIdea(x)}>{x.slice(0, 44)}…</button>)}</div>
        <div className="row"><span className="err">{err || `${idea.length} characters`}</span><button onClick={run} disabled={loading}>{loading ? "Analyzing…" : "Detect overlap →"}</button></div>
      </section>

      {loading && (
        <section className="card pipe">
          {STAGES.map((s, i) => <div key={s} className={i < step ? "st done" : i === step ? "st on" : "st"}><i>{i < step ? "✓" : i + 1}</i><span>{s}</span></div>)}
        </section>
      )}

      {data && (
        <section id="results" className="results">
          <div className="rhead"><div><h2>{verdict}</h2><p className="muted">{data.concepts.length} concepts · {data.overlaps.length} overlapping works · {data.gaps.length} gaps found</p></div><button className="btn2" onClick={download}>↓ Download report</button></div>
          <div className="tabs">{TABS.map((t, i) => <button key={t} className={i === tab ? "tb on" : "tb"} onClick={() => setTab(i)}>{t}</button>)}</div>

          {tab === 0 && (
            <div className="grid3">
              <div className="card center"><Ring value={data.score} />{COLS.map(([k, l]) => <Bar key={k} label={l} v={colAvg(k)} />)}</div>
              <div className="card"><h3>Formal technical queries</h3>{data.queries.map((q, i) => <div key={q} className="chip"><b>Q{i + 1}</b>{q}</div>)}</div>
              <div className="card"><h3>✦ Uncharted territory</h3>{data.gaps.map((g) => <div key={g} className="gap">{g}</div>)}</div>
            </div>)}

          {tab === 1 && (
            <>
              <div className="card"><h3>Blindspot Matrix</h3><p className="muted">Red = heavily explored · Green = uncharted</p>
                <div className="matrix"><div />{COLS.map(([, l]) => <div key={l} className="mh">{l}</div>)}
                  {data.concepts.map((c) => (<><div key={c.name} className="mr">{c.name}</div>
                    {COLS.map(([k]) => <div key={c.name + k} className="cell" style={{ background: heat(c[k]) + "30", border: `1px solid ${heat(c[k])}`, color: heat(c[k]) }}>{Math.round(c[k] * 100)}%</div>)}</>))}
                </div></div>
              <div className="grid2g">
                <div className="card"><h3>Knowledge graph · overlap map</h3><Graph data={data} sel={sel} setSel={setSel} />
                  <div className="legend"><span><i style={{ background: "#fb923c" }} />ArXiv</span><span><i style={{ background: "#facc15" }} />Patent</span><span><i style={{ background: "#4ade80" }} />GitHub</span></div></div>
                <div className="card"><h3>Inspector</h3><Detail sel={sel} /></div>
              </div>
            </>)}

          {tab === 2 && (
            <div className="card"><div className="filters">{["all", "arxiv", "patent", "github"].map((f) => <button key={f} className={f === filter ? "tb on" : "tb"} onClick={() => setFilter(f)}>{f}</button>)}</div>
              {data.overlaps.filter((o) => filter === "all" || o.source === filter).sort((a, b) => b.similarity - a.similarity).map((o) => (
                <a key={o.title} href={o.url} target="_blank" rel="noreferrer" className="ov"><span className={`tag ${o.source}`}>{o.source}</span><span className="ot">{o.title}</span>
                  <div className="mini"><i style={{ width: `${o.similarity * 100}%`, background: heat(o.similarity) }} /></div><b>{Math.round(o.similarity * 100)}%</b></a>))}
            </div>)}

          {tab === 3 && (
            <div className="card"><h3>Overlap-detection accuracy</h3><p className="muted">CogniGap vs. baselines from your evaluation module{data.baselines ? "" : " (not returned by backend)"}.</p>
              {data.baselines && [["Keyword search", data.baselines.keyword, "#64748b"], ["Naive RAG", data.baselines.naive_rag, "#a78bfa"], ["CogniGap · GraphRAG", data.baselines.cognigap, "#22d3ee"]].map(([l, v, c]) => <Bar key={l} label={l} v={v / 100} color={c} />)}</div>)}
        </section>
      )}

      <section id="how" className="how"><h2>How it works</h2>
        <div className="hgrid">{[["Jargon translation", "An LLM converts casual wording into the formal vocabulary used by papers and patents."], ["Multi-source ingestion", "ArXiv, Semantic Scholar, Google Patents and GitHub are searched in parallel."], ["GraphRAG reasoning", "Neo4j + Qdrant enable multi-hop reasoning over entities, not just keywords."], ["Blindspot Matrix", "See overlap and open territory instantly, down to each concept."]].map(([t, d], i) => (
          <div key={t} className="card"><b>0{i + 1}</b><h4>{t}</h4><p className="muted">{d}</p></div>))}</div></section>

      <section id="stack" className="stack">{["Next.js", "FastAPI", "Neo4j", "Qdrant", "LangChain", "Gemini / OpenAI", "ArXiv", "GitHub API"].map((t) => <span key={t}>{t}</span>)}</section>
      <footer>CogniGap · Capstone 2026–27 · MIT WPU · Group 24</footer>
    </>
  );
}
