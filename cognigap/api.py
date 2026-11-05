"""
CogniGap — Unified FastAPI Backend
====================================
REST API backend serving both the Next.js frontend (port 8000) and the
legacy Indolance dashboard (port 5000).
Integrates:
- LLM Query Expansion (Gemini -> Groq -> OpenAI waterfall)
- Multi-domain search (Europe PMC, ArXiv, Google Patents, CrossRef, OpenAlex, GitHub, Web)
- Neo4j Knowledge Graph & Qdrant Vector Store
- GraphRAG Processing Engine (Blindspot Matrix, concept overlaps)
- Comparison Engine (Local & Global TF-IDF cosine similarity, plagiarism detector, insights, references, gaps)
"""

import os
import sys
import json
import asyncio
import hashlib
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cognigap.config import FASTAPI_HOST, FASTAPI_PORT, DATA_DIR
from cognigap.graphrag_engine import GraphRAGEngine
from cognigap.query_expansion import expand_query
from cognigap.data_sources import ArxivSearcher, PatentSearcher, EuropePmcSearcher, rate_limit
from cognigap import neo4j_graph as graph
from chronos.local_reader import LocalReader
from chronos.global_scraper import GlobalScraper
from chronos.comparison_engine import ComparisonEngine
from chronos.utils import logger


# ═══════════════════════════════════════════════════════════
# Startup / Shutdown
# ═══════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup, clean up on shutdown."""
    logger.info("═" * 60)
    logger.info("  COGNIGAP — Starting Unified FastAPI Backend")
    logger.info("═" * 60)

    # Initialize Neo4j (non-blocking if not running yet)
    try:
        graph.initialize_graph()
        logger.info("  ✓ Neo4j connected")
    except Exception as e:
        logger.info(f"  Note: Neo4j local server not active yet ({e}). GraphRAG will operate in in-memory mode.")

    yield

    # Cleanup
    try:
        graph.close_driver()
    except Exception:
        pass
    logger.info("  CogniGap shut down")


# ═══════════════════════════════════════════════════════════
# FastAPI App
# ═══════════════════════════════════════════════════════════

app = FastAPI(
    title="CogniGap API",
    description="AI-Powered Project Novelty and Overlap Detection Engine",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS — allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared engine instances
reader = LocalReader()
scraper = GlobalScraper()
comparison_engine = ComparisonEngine()
graphrag_engine = GraphRAGEngine()
arxiv_searcher = ArxivSearcher()
patent_searcher = PatentSearcher()
europe_pmc_searcher = EuropePmcSearcher()


# ═══════════════════════════════════════════════════════════
# Request/Response Models
# ═══════════════════════════════════════════════════════════

class AnalyzeRequest(BaseModel):
    idea: str
    keywords: str = ""
    tags: str = ""
    topics: str = ""


class ScanRequest(BaseModel):
    idea: str = ""
    keywords: str = ""
    tags: str = ""
    topics: str = ""


# ═══════════════════════════════════════════════════════════
# CogniGap Unified Endpoint
# ═══════════════════════════════════════════════════════════

@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    """
    Unified CogniGap & Indolance Analysis Pipeline:
    1. LLM Query Expansion (formal technical queries & concepts)
    2. Multi-domain search (Europe PMC, ArXiv, Google Patents, CrossRef, OpenAlex, GitHub, Web)
    3. Local file scanning (Comparison with user's local projects)
    4. Indolance Comparison Engine (Dual local/global TF-IDF originality scores, plagiarism sources, insights, references)
    5. GraphRAG Processing Engine (Concept overlap, Blindspot Matrix, Knowledge Graph nodes)
    6. Returns unified JSON supporting both modern Next.js and Flask dashboards.
    """
    idea = req.idea.strip()
    if not idea or len(idea) < 10:
        raise HTTPException(400, "Please provide a more detailed project description (at least 10 characters)")

    logger.info("═" * 60)
    logger.info("  COGNIGAP — Full Unified Analysis Pipeline")
    logger.info("═" * 60)
    logger.info(f"  Idea: {idea[:100]}...")

    # Parse user keywords and tags
    user_kws = [k.strip().lower() for k in req.keywords.split(",") if k.strip()] if req.keywords else []
    user_tags = [t.strip().lower() for t in req.tags.split(",") if t.strip()] if req.tags else []
    all_keywords = list(dict.fromkeys(user_kws + user_tags))

    # Step 1: LLM Query Expansion
    expansion = expand_query(idea)
    queries = expansion.get("expanded_queries", [idea[:100]])
    concepts = expansion.get("concepts", [])

    # Step 2: Multi-domain search
    all_results = []

    # If user provided explicit topics, also search them
    extra_topics = [t.strip() for t in req.topics.split(",") if t.strip()] if req.topics else []
    search_queries = list(dict.fromkeys(queries[:3] + extra_topics[:2]))

    for i, query in enumerate(search_queries):
        logger.info(f"  [{i+1}/{len(search_queries)}] Searching: '{query[:60]}...'")

        # Free, reliable academic literature
        all_results.extend(europe_pmc_searcher.search(query, limit=10))
        rate_limit()
        all_results.extend(arxiv_searcher.search(query, limit=10))
        rate_limit()
        all_results.extend(patent_searcher.search(query, limit=8))
        rate_limit()
        all_results.extend(scraper.search_crossref(query, limit=8))
        rate_limit()
        all_results.extend(scraper.search_openalex(query, limit=8))
        rate_limit()
        all_results.extend(scraper.search_github(query, limit=8))
        rate_limit()
        all_results.extend(scraper.search_semantic_scholar(query, limit=8))
        rate_limit()

    # Deep GitHub search
    concept_kws = [w for w in concepts if " " not in w]
    deep_kws = list(dict.fromkeys(all_keywords + concept_kws))[:6]
    github_deep = scraper.search_github_deep(idea, deep_kws)
    all_results.extend(github_deep)

    # Web search for the idea itself
    if len(idea) > 10:
        all_results.extend(scraper.search_web(idea[:150]))

    # Deduplicate results
    all_results = scraper._deduplicate(all_results)
    all_results = [e for e in all_results if e.get("url")]
    logger.info(f"  Total unique search results: {len(all_results)}")

    # Update global scraper cache
    scraper.global_trends = all_results
    scraper.save_trends()

    # Step 3: Local scanning
    reader.scan_all()

    # Step 4: Indolance Comparison Engine (Computes true TF-IDF Local & Global Originality scores!)
    comp_results = comparison_engine.analyze(
        reader, scraper,
        user_idea=idea,
        user_keywords=all_keywords
    )

    # Step 5: GraphRAG Processing Engine (Computes Blindspot Matrix & Overlaps)
    graphrag_results = graphrag_engine.process(idea, all_results)

    # Step 6: Build Unified Response
    local_score = comp_results.get("local_originality_score", 100.0)
    comp_global = comp_results.get("global_originality_score", 100.0)
    graphrag_score = graphrag_results.get("originality_score")
    if graphrag_score is not None and comp_global is not None:
        global_score = round(0.5 * comp_global + 0.5 * graphrag_score, 1)
    else:
        global_score = comp_global or graphrag_score or 100.0

    # Combine gaps cleanly
    combined_gaps = []
    seen_gaps = set()
    for g in (comp_results.get("gaps", []) + graphrag_results.get("gaps", [])):
        txt = g if isinstance(g, str) else g.get("topic", "") if isinstance(g, dict) else str(g)
        if txt and txt.lower() not in seen_gaps:
            seen_gaps.add(txt.lower())
            combined_gaps.append(txt)

    response = {
        # Originality Scores (True TF-IDF math from Indolance ComparisonEngine)
        "originality_score": global_score,
        "score": global_score,
        "local_originality_score": local_score,
        "global_originality_score": global_score,
        "local_plagiarism_pct": comp_results.get("local_plagiarism_pct", round(100 - local_score, 1)),
        "global_plagiarism_pct": comp_results.get("global_plagiarism_pct", round(100 - global_score, 1)),
        "local_file_count": comp_results.get("local_file_count", 0),
        "global_result_count": len(all_results),
        "evidence_count": len(all_results),
        "assessment_confidence": graphrag_results.get("assessment_confidence", "high"),
        "status_counts": comp_results.get("status_counts", {
            "already_exists": 0, "similar_work": 0, "original": 0
        }),

        # CogniGap GraphRAG & Blindspot Matrix
        "concepts": graphrag_results.get("concepts", []),
        "overlaps": graphrag_results.get("overlaps", []),
        "expanded_queries": graphrag_results.get("expanded_queries", queries),
        "queries": graphrag_results.get("expanded_queries", queries),
        "formal_summary": graphrag_results.get("formal_summary", ""),
        "gaps": combined_gaps[:10],

        # Indolance Core Features
        "plagiarism_sources": comp_results.get("plagiarism_sources", []),
        "insights": comp_results.get("insights", {}),
        "references": comp_results.get("references", {}),
        "local_similar_files": comp_results.get("local_similar_files", []),
        "connection_map": comp_results.get("connection_map", ""),
        "overlap_keywords": comp_results.get("overlap_keywords", []),
        "total_user_keywords": comp_results.get("total_user_keywords", len(all_keywords)),
        "total_global_keywords": comp_results.get("total_global_keywords", 0),
        "overlap_count": comp_results.get("overlap_count", 0),

        # Legacy wrapper for Flask UI compatibility
        "success": True,
        "results": comp_results,
        "timestamp": datetime.now().isoformat(),
    }

    logger.info(f"  ✓ Analysis complete. Local: {local_score}% | Global: {global_score}% | Concepts: {len(response['concepts'])}")
    logger.info("═" * 60)
    return response


@app.get("/health")
async def health():
    """Health check endpoint."""
    neo4j_ok = False
    try:
        neo4j_ok = graph.test_connection()
    except Exception:
        pass

    return {
        "status": "ok",
        "neo4j": "connected" if neo4j_ok else "disconnected",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/stats")
async def stats():
    """Get knowledge graph statistics."""
    try:
        kg_stats = graph.get_knowledge_graph_stats()
        return {"status": "ok", "graph": kg_stats}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ═══════════════════════════════════════════════════════════
# Legacy Indolance API Endpoints (Flask dashboard compatibility)
# ═══════════════════════════════════════════════════════════

@app.post("/api/scan")
async def api_scan(req: ScanRequest):
    """Legacy: Trigger local file scan."""
    try:
        kb = reader.scan_all()
        return {
            "success": True,
            "message": f"Scanned {len(kb)} files",
            "total_files": len(kb),
            "keywords": reader.get_all_keywords()[:30],
            "timeline": reader.get_keyword_timeline(),
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/scrape")
async def api_scrape(req: ScanRequest):
    """Legacy: Trigger API-based searching."""
    try:
        topics = [t.strip() for t in req.topics.split(",") if t.strip()] if req.topics else []
        if topics:
            scraper.topics = topics

        idea_keywords = [k.strip().lower() for k in req.keywords.split(",") if k.strip()] if req.keywords else []
        trends = scraper.scrape_all(idea_text=req.idea, idea_keywords=idea_keywords)

        source_counts = {}
        for t in trends:
            src = t.get("source_label", t.get("source", "unknown"))
            source_counts[src] = source_counts.get(src, 0) + 1

        return {
            "success": True,
            "message": f"Found {len(trends)} results from {len(source_counts)} sources",
            "total_results": len(trends),
            "top_keywords": scraper.get_keyword_frequencies()[:20],
            "source_counts": source_counts,
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/analyze")
async def api_analyze_legacy(req: ScanRequest):
    """Legacy route: routes through the unified pipeline."""
    return await analyze(AnalyzeRequest(
        idea=req.idea,
        keywords=req.keywords,
        tags=req.tags,
        topics=req.topics,
    ))


@app.get("/api/results")
async def api_results():
    """Legacy: Get latest analysis results."""
    results = comparison_engine.load_results()
    if results:
        return {"success": True, "results": results}
    return {"success": False, "message": "No results yet."}


@app.get("/api/status")
async def api_status():
    """Legacy: Check data status."""
    local_path = os.path.join(DATA_DIR, "local_keywords.json")
    global_path = os.path.join(DATA_DIR, "global_trends.json")
    results_path = os.path.join(DATA_DIR, "analysis_results.json")
    return {
        "has_local_data": os.path.exists(local_path),
        "has_global_data": os.path.exists(global_path),
        "has_results": os.path.exists(results_path),
    }


# ═══════════════════════════════════════════════════════════
# Main Entry Point
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print()
    print("═" * 60)
    print("  COGNIGAP — AI-Powered Novelty Detection Engine")
    print("  FastAPI Backend: http://localhost:8000")
    print("  API Docs:        http://localhost:8000/docs")
    print("  Health Check:    http://localhost:8000/health")
    print("═" * 60)
    print()

    uvicorn.run(
        "cognigap.api:app",
        host=FASTAPI_HOST,
        port=FASTAPI_PORT,
        reload=True,
    )
