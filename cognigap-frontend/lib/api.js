// ===== CogniGap API Layer =====
const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const ENDPOINT = "/analyze";

function normalize(d) {
  const globalScore = Math.round(
    d.global_originality_score ?? d.originality_score ?? d.score ?? 100
  );
  const localScore = Math.round(d.local_originality_score ?? 100);

  return {
    queries: d.expanded_queries ?? d.queries ?? [],
    score: globalScore,
    localScore: localScore,
    globalScore: globalScore,
    localPlagiarismPct: d.local_plagiarism_pct ?? Math.max(0, 100 - localScore),
    globalPlagiarismPct: d.global_plagiarism_pct ?? Math.max(0, 100 - globalScore),
    localFileCount: d.local_file_count ?? 0,
    globalResultCount: d.global_result_count ?? d.evidence_count ?? 0,
    assessmentConfidence: d.assessment_confidence ?? "high",
    evidenceCount: d.evidence_count ?? 0,
    statusCounts: d.status_counts ?? {
      already_exists: 0,
      similar_work: 0,
      original: 0,
    },
    concepts: (d.concepts ?? d.matrix ?? []).map((c) => ({
      name: c.name,
      papers: c.papers ?? 0,
      patents: c.patents ?? 0,
      code: c.code ?? 0,
    })),
    overlaps: (d.overlaps ?? []).map((o) => ({
      ...o,
      concepts: o.concepts ?? [],
      url: o.url ?? "#",
    })),
    plagiarismSources: d.plagiarism_sources ?? [],
    insights: d.insights ?? { pros: [], cons: [], recommendation: "" },
    references: d.references ?? { papers: [], repositories: [], web: [] },
    localFiles: d.local_similar_files ?? [],
    gaps: d.gaps ?? [],
    baselines: d.baselines ?? null,
  };
}

export async function analyze(payload) {
  const body = typeof payload === "string" ? { idea: payload } : payload;
  const res = await fetch(BASE + ENDPOINT, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`Backend error ${res.status}`);
  }
  return normalize(await res.json());
}
