// ===== CogniGap API layer — the ONLY file to edit when connecting your backend =====
// .env.local -> NEXT_PUBLIC_API_URL=http://<backend-ip>:8000   (empty = demo data)
const BASE = process.env.NEXT_PUBLIC_API_URL || "";
const ENDPOINT = "/analyze"; // your FastAPI route

// Expected JSON (rename fields in normalize() if yours differ):
// { expanded_queries:[str], originality_score:0-100,
//   concepts:[{name, papers, patents, code}]            // 0-1 overlap per source
//   overlaps:[{title, source:"arxiv|patent|github", url, similarity:0-1, concepts:[name]}],
//   gaps:[str], baselines:{keyword:0-100, naive_rag:0-100, cognigap:0-100} }
function normalize(d) {
  return {
    queries: d.expanded_queries ?? d.queries ?? [],
    score: Math.round(d.originality_score ?? d.score ?? 0),
    concepts: (d.concepts ?? d.matrix ?? []).map((c) => ({ name: c.name, papers: c.papers ?? 0, patents: c.patents ?? 0, code: c.code ?? 0 })),
    overlaps: (d.overlaps ?? []).map((o) => ({ ...o, concepts: o.concepts ?? [], url: o.url ?? "#" })),
    gaps: d.gaps ?? [],
    baselines: d.baselines ?? null,
  };
}

export async function analyze(idea) {
  if (!BASE) return mock();
  const res = await fetch(BASE + ENDPOINT, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ idea }), // change key if backend expects another name
  });
  if (!res.ok) throw new Error(`Backend error ${res.status}`);
  return normalize(await res.json());
}

const mock = () => new Promise((r) => setTimeout(() => r(normalize({
  expanded_queries: [
    "retrieval-augmented generation over heterogeneous knowledge graphs",
    "multi-hop reasoning for prior-art novelty assessment",
    "semantic vocabulary normalization via large language models",
  ],
  originality_score: 68,
  concepts: [
    { name: "Query expansion", papers: 0.82, patents: 0.35, code: 0.6 },
    { name: "Knowledge graph", papers: 0.9, patents: 0.55, code: 0.74 },
    { name: "GraphRAG reasoning", papers: 0.58, patents: 0.12, code: 0.41 },
    { name: "Patent prior-art", papers: 0.3, patents: 0.7, code: 0.08 },
    { name: "Blindspot visualization", papers: 0.07, patents: 0.04, code: 0.1 },
  ],
  overlaps: [
    { title: "From Local to Global: A Graph RAG Approach", source: "arxiv", similarity: 0.81, concepts: ["Knowledge graph", "GraphRAG reasoning"] },
    { title: "LLM query rewriting for scholarly search", source: "arxiv", similarity: 0.72, concepts: ["Query expansion"] },
    { title: "Patent novelty search using embeddings", source: "patent", similarity: 0.66, concepts: ["Patent prior-art", "Knowledge graph"] },
    { title: "microsoft/graphrag", source: "github", similarity: 0.62, concepts: ["GraphRAG reasoning", "Knowledge graph"] },
    { title: "langchain-ai/langchain", source: "github", similarity: 0.48, concepts: ["Query expansion"] },
  ],
  gaps: ["Unified overlap scoring across papers + patents + code", "Interactive gap visualization built for students", "Jargon-gap translation before prior-art search"],
  baselines: { keyword: 41, naive_rag: 58, cognigap: 84 },
}), 3200));
