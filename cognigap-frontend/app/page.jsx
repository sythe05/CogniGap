"use client";
import React, { Fragment, useEffect, useMemo, useState } from "react";
import { analyze } from "../lib/api";

const STAGES = [
  "Informal idea",
  "LLM query expansion",
  "Multi-source search",
  "TF-IDF & Embeddings",
  "Knowledge graph ingestion",
  "GraphRAG reasoning",
  "Blindspot & Originality report",
];

const COLS = [
  ["papers", "Papers"],
  ["patents", "Patents"],
  ["code", "Code"],
];

const avg = (c) => (c.papers + c.patents + c.code) / 3;
const heat = (v) => `hsl(${Math.round(150 - v * 150)} 80% 55%)`;

function Ring({ value, label = "ORIGINALITY", color = "#7c5cff" }) {
  const r = 58;
  const c = 2 * Math.PI * r;
  const ringValue = value == null ? 0 : Math.max(0, Math.min(100, value));

  return (
    <svg width="150" height="150" viewBox="0 0 160 160">
      <defs>
        <linearGradient id={`rg-${label}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor={color} />
          <stop offset="100%" stopColor="#22d3ee" />
        </linearGradient>
      </defs>
      <circle cx="80" cy="80" r={r} className="ring-bg" />
      <circle
        cx="80"
        cy="80"
        r={r}
        className="ring-fg"
        stroke={`url(#rg-${label})`}
        strokeDasharray={c}
        strokeDashoffset={c * (1 - ringValue / 100)}
      />
      <text x="80" y="82" textAnchor="middle" className="ring-t">
        {value == null ? "—" : `${Math.round(value)}%`}
      </text>
      <text x="80" y="104" textAnchor="middle" className="ring-s">
        {label}
      </text>
    </svg>
  );
}

function Graph({ data, sel, setSel }) {
  const { nodes, edges } = useMemo(() => {
    const cx = 320;
    const cy = 210;
    const n = Math.max(1, (data.concepts || []).length);
    const ns = [];
    const es = [];
    const pos = {};

    (data.concepts || []).forEach((c, i) => {
      const a = (i / n) * 2 * Math.PI - Math.PI / 2;
      pos[c.name] = { x: cx + 115 * Math.cos(a), y: cy + 115 * Math.sin(a), a };
      ns.push({
        id: c.name,
        type: "concept",
        item: c,
        ...pos[c.name],
        r: 18 + avg(c) * 10,
        color: heat(avg(c)),
      });
      es.push({ x1: cx, y1: cy, x2: pos[c.name].x, y2: pos[c.name].y });
    });

    const overlapsList = (data.overlaps || []).slice(0, 16);
    overlapsList.forEach((o, i) => {
      const links = (o.concepts || []).filter((k) => pos[k]);
      const a = links.length
        ? links.reduce((s, k) => s + pos[k].a, 0) / links.length +
          (i % 2 ? 0.22 : -0.22)
        : (i / Math.max(1, overlapsList.length)) * 6.28;
      const p = { x: cx + 195 * Math.cos(a), y: cy + 185 * Math.sin(a) };
      ns.push({
        id: "s" + i,
        type: "source",
        item: o,
        ...p,
        r: 9,
        color:
          {
            arxiv: "#fb923c",
            patent: "#facc15",
            github: "#4ade80",
            europe_pmc: "#38bdf8",
            crossref: "#c084fc",
          }[o.source] || "#aaa",
      });
      links.forEach((k) =>
        es.push({ x1: pos[k].x, y1: pos[k].y, x2: p.x, y2: p.y, dim: true })
      );
    });

    return { nodes: ns, edges: es };
  }, [data]);

  return (
    <svg viewBox="0 0 640 420" className="graph">
      {edges.map((e, i) => (
        <line key={i} {...e} className={e.dim ? "edge dim" : "edge"} />
      ))}
      <circle cx="320" cy="210" r="26" className="core" />
      <text x="320" y="214" textAnchor="middle" className="gt">
        YOUR IDEA
      </text>
      {nodes.map((n) => (
        <g
          key={n.id}
          className={"node" + (sel?.id === n.id ? " act" : "")}
          onClick={() => setSel(n)}
        >
          <circle
            cx={n.x}
            cy={n.y}
            r={n.r}
            fill={n.color}
            fillOpacity=".25"
            stroke={n.color}
            strokeWidth="2"
          />
          {n.type === "concept" && (
            <text x={n.x} y={n.y + n.r + 14} textAnchor="middle" className="gl">
              {n.id.length > 20 ? n.id.slice(0, 18) + "…" : n.id}
            </text>
          )}
        </g>
      ))}
    </svg>
  );
}

function Detail({ sel }) {
  if (!sel) return <p className="muted">Click any node in the graph to inspect it.</p>;
  if (sel.type === "concept") {
    const c = sel.item;
    const a = avg(c);
    return (
      <div>
        <span className="tag" style={{ color: heat(a) }}>
          {a > 0.6 ? "Heavily covered" : a > 0.3 ? "Partly explored" : "Uncharted"}
        </span>
        <h4>{c.name}</h4>
        <p className="muted">Estimated novelty: {Math.round((1 - a) * 100)}%</p>
        {COLS.map(([k, l]) => (
          <Bar key={k} label={l} v={c[k]} />
        ))}
      </div>
    );
  }
  const o = sel.item;
  return (
    <div>
      <span className={`tag ${o.source}`}>{o.source}</span>
      <h4>{o.title}</h4>
      <p className="muted">Similarity: {Math.round((o.similarity || 0) * 100)}%</p>
      {o.url && o.url !== "#" && (
        <a className="btn2" href={o.url} target="_blank" rel="noreferrer" style={{ marginTop: 8 }}>
          Open source ↗
        </a>
      )}
    </div>
  );
}

const Bar = ({ label, v, color }) => (
  <div className="bar">
    <span>{label}</span>
    <div>
      <i
        style={{
          width: `${Math.round((v || 0) * 100)}%`,
          background: color || heat(v || 0),
        }}
      />
    </div>
    <b>{Math.round((v || 0) * 100)}%</b>
  </div>
);

export default function Home() {
  const [idea, setIdea] = useState("");
  const [keywords, setKeywords] = useState("");
  const [tags, setTags] = useState("");
  const [topics, setTopics] = useState("");
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState(0);
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [sel, setSel] = useState(null);
  const [filter, setFilter] = useState("all");

  useEffect(() => {
    const m = (e) => {
      document.documentElement.style.setProperty("--mx", e.clientX + "px");
      document.documentElement.style.setProperty("--my", e.clientY + "px");
    };
    window.addEventListener("mousemove", m);
    return () => window.removeEventListener("mousemove", m);
  }, []);

  async function run() {
    if (idea.trim().length < 10)
      return setErr("Please describe your idea in a bit more detail (at least 10 characters).");
    setErr("");
    setData(null);
    setLoading(true);
    setStep(0);
    setSel(null);

    const t = setInterval(
      () => setStep((s) => Math.min(s + 1, STAGES.length - 1)),
      650
    );

    try {
      const res = await analyze({ idea, keywords, tags, topics });
      setData(res);
      setTimeout(
        () =>
          document
            .getElementById("results")
            ?.scrollIntoView({ behavior: "smooth" }),
        120
      );
    } catch (e) {
      setErr(e.message || "Something went wrong during analysis.");
    } finally {
      clearInterval(t);
      setLoading(false);
    }
  }

  const verdict = data
    ? data.score == null
      ? "Insufficient evidence"
      : data.score >= 75
      ? "Largely Novel Idea"
      : data.score >= 45
      ? "Partially Explored Territory"
      : "Heavily Covered Prior Art"
    : "";

  return (
    <>
      <div className="spot" />
      <div className="gridbg" />
      <nav className="nav">
        <b className="logo">
          <span className="dot" />
          CogniGap
        </b>
      </nav>

      <header className="hero">
        <h1>
          Is your idea <em>actually</em> new?
        </h1>
        <p>
          Translate informal project ideas into formal research vocabulary. Cross-reference academic papers,
          patents, and GitHub repositories with GraphRAG and TF-IDF dual-scoring.
        </p>
      </header>

      {/* Input Section */}
      <section id="analyze" className="card input">
        <textarea
          value={idea}
          onChange={(e) => setIdea(e.target.value)}
          rows={4}
          placeholder="Describe your research or project idea in everyday English (e.g., real-time medicinal plant recognition on mobile using deep learning)..."
        />

        <div className="input-grid">
          <div className="input-field">
            <label htmlFor="kwInput">Keywords (comma-separated)</label>
            <input
              id="kwInput"
              type="text"
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
              placeholder="e.g. computer vision, medicinal plants, mobile AI"
            />
          </div>
          <div className="input-field">
            <label htmlFor="tagInput">Tags / Categories (comma-separated)</label>
            <input
              id="tagInput"
              type="text"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              placeholder="e.g. machine learning, botany, android, edge computing"
            />
          </div>
        </div>

        <div className="input-field" style={{ marginTop: 12 }}>
          <label htmlFor="topicInput">Search Topics for Database Lookup (optional)</label>
          <input
            id="topicInput"
            type="text"
            value={topics}
            onChange={(e) => setTopics(e.target.value)}
            placeholder="e.g. Botanical Image Classification, On-device Neural Networks, Plant Morphology"
          />
        </div>

        <div className="row" style={{ marginTop: 16 }}>
          <span className="err">{err || `${idea.length} characters`}</span>
          <button onClick={run} disabled={loading}>
            {loading ? "Analyzing prior art…" : "Detect overlap →"}
          </button>
        </div>
      </section>

      {/* Pipeline Progress */}
      {loading && (
        <section className="card pipe">
          {STAGES.map((s, i) => (
            <div
              key={s}
              className={i < step ? "st done" : i === step ? "st on" : "st"}
            >
              <i>{i < step ? "✓" : i + 1}</i>
              <span>{s}</span>
            </div>
          ))}
        </section>
      )}

      {/* Scrollable Results */}
      {data && (
        <div id="results" className="results">
          {/* Header Summary */}
          <div className="rhead">
            <div>
              <h2>{verdict}</h2>
              <p className="muted">
                {data.concepts?.length || 0} architectural concepts · {data.overlaps?.length || 0} overlapping works · {data.evidenceCount || 0} sources searched
              </p>
            </div>
          </div>

          {/* 1. Dual Originality Scores */}
          <section className="card">
            <div className="section-title">
              Dual Originality Scores
              <span className="badge">TF-IDF Vector Math</span>
            </div>
            <div className="dual-score-row">
              <div className="score-box">
                <h3>Global Originality</h3>
                <p className="sub">vs academic papers, patents &amp; GitHub repos</p>
                <Ring value={data.globalScore} label="GLOBAL NOVELTY" color="#7c5cff" />
                <div className="score-meta">
                  <div>
                    <b>{data.globalPlagiarismPct}%</b>
                    <span>Overlap / Prior Art</span>
                  </div>
                  <div>
                    <b>{data.globalResultCount}</b>
                    <span>Sources Checked</span>
                  </div>
                </div>
              </div>

              <div className="score-box">
                <h3>Local Originality</h3>
                <p className="sub">vs your local files &amp; prior projects</p>
                <Ring value={data.localScore} label="LOCAL NOVELTY" color="#22d3ee" />
                <div className="score-meta">
                  <div>
                    <b>{data.localPlagiarismPct}%</b>
                    <span>Local Overlap</span>
                  </div>
                  <div>
                    <b>{data.localFileCount}</b>
                    <span>Files Compared</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Status Breakdown Bar */}
            <div className="status-pills">
              <div className="status-pill red">
                <span className="dot" style={{ background: "#ef4444", width: 8, height: 8 }} />
                <span>{data.statusCounts?.already_exists || 0} Already Exists</span>
              </div>
              <div className="status-pill amber">
                <span className="dot" style={{ background: "#f59e0b", width: 8, height: 8 }} />
                <span>{data.statusCounts?.similar_work || 0} Similar Work</span>
              </div>
              <div className="status-pill green">
                <span className="dot" style={{ background: "#22c55e", width: 8, height: 8 }} />
                <span>{data.statusCounts?.original || 0} Potentially Original</span>
              </div>
            </div>
          </section>

          {/* 2. Blindspot Matrix */}
          <section className="card">
            <div className="section-title">
              Blindspot Matrix
              <span className="badge">Multi-Source Prior Art</span>
            </div>
            <p className="muted" style={{ marginBottom: 12 }}>
              Red indicates heavy existing prior-art coverage; green indicates uncharted territory.
            </p>
            <div className="matrix">
              <div />
              {COLS.map(([, l]) => (
                <div key={l} className="mh">
                  {l}
                </div>
              ))}
              {(data.concepts || []).map((c) => (
                <Fragment key={c.name}>
                  <div className="mr">{c.name}</div>
                  {COLS.map(([k]) => (
                    <div
                      key={c.name + k}
                      className="cell"
                      style={{
                        background: heat(c[k]) + "28",
                        border: `1px solid ${heat(c[k])}`,
                        color: heat(c[k]),
                      }}
                    >
                      {Math.round((c[k] || 0) * 100)}%
                    </div>
                  ))}
                </Fragment>
              ))}
            </div>
          </section>

          {/* 3. Knowledge Graph & Inspector */}
          <section className="card">
            <div className="section-title">
              Knowledge Graph · Multi-Hop Overlap Map
              <span className="badge">GraphRAG</span>
            </div>
            <div className="grid2g">
              <div>
                <Graph data={data} sel={sel} setSel={setSel} />
                <div className="legend" style={{ marginTop: 12 }}>
                  <span>
                    <i style={{ background: "#fb923c" }} />
                    ArXiv
                  </span>
                  <span>
                    <i style={{ background: "#facc15" }} />
                    Patent
                  </span>
                  <span>
                    <i style={{ background: "#4ade80" }} />
                    GitHub
                  </span>
                  <span>
                    <i style={{ background: "#38bdf8" }} />
                    Europe PMC
                  </span>
                </div>
              </div>
              <div className="score-box" style={{ textAlign: "left" }}>
                <h3>Node Inspector</h3>
                <Detail sel={sel} />
              </div>
            </div>
          </section>

          {/* 4. Formal Technical Queries */}
          {data.queries?.length > 0 && (
            <section className="card">
              <div className="section-title">
                Formal Technical Queries
                <span className="badge">LLM Expansion</span>
              </div>
              <p className="muted" style={{ marginBottom: 12 }}>
                Translates casual student vocabulary into standardized research and patent terminology:
              </p>
              {data.queries.map((q, i) => (
                <div key={q + i} className="chip">
                  <b>Q{i + 1}</b>
                  <span>{q}</span>
                </div>
              ))}
            </section>
          )}

          {/* 5. Plagiarism Sources & Prior Art */}
          <section className="card">
            <div className="section-title">
              Plagiarism Sources &amp; Matching Works
              <span className="badge">Direct Matches</span>
            </div>
            <div className="filters">
              {["all", "arxiv", "patent", "github", "europe_pmc"].map((f) => (
                <button
                  key={f}
                  className={f === filter ? "tb on" : "tb"}
                  onClick={() => setFilter(f)}
                >
                  {f === "europe_pmc" ? "Europe PMC" : f}
                </button>
              ))}
            </div>

            {/* Overlapping works matching the filter */}
            {(data.overlaps || [])
              .filter((o) => filter === "all" || o.source === filter)
              .sort((a, b) => (b.similarity || 0) - (a.similarity || 0))
              .map((o, idx) => (
                <a
                  key={o.title + idx}
                  href={o.url}
                  target="_blank"
                  rel="noreferrer"
                  className="ov"
                >
                  <span className={`tag ${o.source}`}>{o.source}</span>
                  <span className="ot">{o.title}</span>
                  <div className="mini">
                    <i
                      style={{
                        width: `${Math.round((o.similarity || 0) * 100)}%`,
                        background: heat(o.similarity || 0),
                      }}
                    />
                  </div>
                  <b>{Math.round((o.similarity || 0) * 100)}%</b>
                </a>
              ))}

            {/* Plagiarism sources with snippets from ComparisonEngine */}
            {data.plagiarismSources?.length > 0 && (
              <div style={{ marginTop: 20 }}>
                <h3 style={{ marginBottom: 10 }}>Detailed Plagiarism Citations:</h3>
                {data.plagiarismSources.slice(0, 8).map((p, idx) => (
                  <div key={p.title + idx} className="plag-item">
                    <div className="plag-top">
                      <span className="tag">{p.source_label || p.source_type || "Source"}</span>
                      <span
                        className="plag-pct"
                        style={{ color: heat((p.similarity_pct || 0) / 100) }}
                      >
                        {p.similarity_pct}% similarity
                      </span>
                    </div>
                    <a
                      href={p.url || "#"}
                      target="_blank"
                      rel="noreferrer"
                      style={{ color: "#fff", fontWeight: 600, textDecoration: "none" }}
                    >
                      {p.title} ↗
                    </a>
                    {p.snippet && <p className="muted">{p.snippet}</p>}
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* 6. Project Insights */}
          {data.insights && (data.insights.pros?.length > 0 || data.insights.cons?.length > 0) && (
            <section className="card">
              <div className="section-title">
                Project Insights &amp; Viability Assessment
                <span className="badge">Advisory</span>
              </div>
              <div className="insights-grid">
                <div className="insight-col">
                  <h4 style={{ color: "#4ade80" }}>✓ Project Strengths</h4>
                  <ul>
                    {data.insights.pros.map((pro, i) => {
                      if (typeof pro === "string") return <li key={i}>{pro}</li>;
                      return (
                        <li key={i}>
                          <b>{pro.icon ? `${pro.icon} ` : ""}{pro.title || "Strength"}</b>
                          {pro.detail && <p className="muted" style={{ marginTop: 3 }}>{pro.detail}</p>}
                        </li>
                      );
                    })}
                  </ul>
                </div>
                <div className="insight-col">
                  <h4 style={{ color: "#fbbf24" }}>⚠ Concerns &amp; Challenges</h4>
                  <ul>
                    {data.insights.cons.map((con, i) => {
                      if (typeof con === "string") return <li key={i}>{con}</li>;
                      return (
                        <li key={i}>
                          <b>{con.icon ? `${con.icon} ` : ""}{con.title || "Concern"}</b>
                          {con.detail && <p className="muted" style={{ marginTop: 3 }}>{con.detail}</p>}
                        </li>
                      );
                    })}
                  </ul>
                </div>
              </div>
              {data.insights.recommendation && (
                <div className="recommendation-box">
                  <b>Recommendation: </b>
                  <span>
                    {typeof data.insights.recommendation === "string"
                      ? data.insights.recommendation
                      : data.insights.recommendation.detail ||
                        data.insights.recommendation.title ||
                        JSON.stringify(data.insights.recommendation)}
                  </span>
                  {data.insights.recommendation_detail && (
                    <p className="muted" style={{ marginTop: 4 }}>
                      {data.insights.recommendation_detail}
                    </p>
                  )}
                </div>
              )}
            </section>
          )}

          {/* 7. Reference Materials */}
          {data.references && (
            <section className="card">
              <div className="section-title">
                Reference Materials
                <span className="badge">Curated Reading</span>
              </div>
              <div className="ref-list">
                {/* Papers */}
                {(data.references.papers || []).slice(0, 5).map((paper, i) => (
                  <a
                    key={paper.title + i}
                    href={paper.url || "#"}
                    target="_blank"
                    rel="noreferrer"
                    className="ref-item"
                  >
                    <div className="ref-header">
                      <span className="tag" style={{ color: "#38bdf8" }}>Academic Paper</span>
                      {paper.year && <span className="muted">{paper.year}</span>}
                    </div>
                    <div className="ref-title">{paper.title} ↗</div>
                    {paper.snippet && <div className="ref-snip">{paper.snippet.slice(0, 180)}…</div>}
                  </a>
                ))}

                {/* Repositories */}
                {(data.references.repositories || []).slice(0, 5).map((repo, i) => (
                  <a
                    key={repo.title + i}
                    href={repo.url || "#"}
                    target="_blank"
                    rel="noreferrer"
                    className="ref-item"
                  >
                    <div className="ref-header">
                      <span className="tag" style={{ color: "#4ade80" }}>GitHub Repository</span>
                      {repo.stars != null && <span className="muted">★ {repo.stars}</span>}
                    </div>
                    <div className="ref-title">{repo.title} ↗</div>
                    {repo.snippet && <div className="ref-snip">{repo.snippet.slice(0, 180)}…</div>}
                  </a>
                ))}
              </div>
            </section>
          )}

          {/* 8. Gap Finder */}
          {data.gaps?.length > 0 && (
            <section className="card">
              <div className="section-title">
                Gap Finder · Uncharted Opportunities
                <span className="badge">Opportunities</span>
              </div>
              <p className="muted" style={{ marginBottom: 12 }}>
                Identified gaps where existing literature and repositories are sparse:
              </p>
              {data.gaps.map((g, i) => (
                <div key={i} className="gap">
                  {typeof g === "string" ? g : g.topic || JSON.stringify(g)}
                </div>
              ))}
            </section>
          )}

          {/* 9. Local File Matches */}
          {data.localFiles?.length > 0 && (
            <section className="card">
              <div className="section-title">
                Local Workspace Matches
                <span className="badge">Internal Similarity</span>
              </div>
              {data.localFiles.map((f, i) => (
                <div key={i} className="plag-item">
                  <div className="plag-top">
                    <span className="tag">{f.status || "Local File"}</span>
                    <span className="plag-pct">{Math.round((f.similarity || 0) * 100)}%</span>
                  </div>
                  <b>{f.filename || f.source_file}</b>
                  {f.snippet && <p className="muted">{f.snippet}</p>}
                </div>
              ))}
            </section>
          )}
        </div>
      )}

      {/* How it works */}
      <section id="how" className="how">
        <h2>How CogniGap Works</h2>
        <div className="hgrid">
          {[
            [
              "Jargon translation",
              "An LLM converts casual project ideas into formal technical vocabulary used by papers and patents.",
            ],
            [
              "Multi-source search",
              "Europe PMC, ArXiv, Google Patents, CrossRef, OpenAlex, and GitHub searched simultaneously.",
            ],
            [
              "GraphRAG reasoning",
              "Neo4j Knowledge Graph enables multi-hop reasoning over architectural entities, not just keywords.",
            ],
            [
              "Dual-scoring & Blindspot",
              "TF-IDF cosine similarity generates dual local/global scores alongside the interactive Blindspot Matrix.",
            ],
          ].map(([t, d], i) => (
            <div key={t} className="card">
              <b>0{i + 1}</b>
              <h4>{t}</h4>
              <p className="muted">{d}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="stack" className="stack">
        {[
          "Next.js",
          "FastAPI",
          "Neo4j",
          "GraphRAG",
          "TF-IDF Vectorizer",
          "Europe PMC",
          "Google Patents",
          "ArXiv",
          "GitHub API",
        ].map((t) => (
          <span key={t}>{t}</span>
        ))}
      </section>

      <footer>CogniGap · 2026</footer>
    </>
  );
}
