"""
CogniGap — FastAPI Backend
============================
REST API backend that serves the Next.js frontend.
Implements the /analyze endpoint and integrates all CogniGap modules.

Also keeps the legacy Flask dashboard running on port 5000 for backward compatibility.
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
from cognigap.data_sources import ArxivSearcher, PatentSearcher, rate_limit
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
    logger.info("  COGNIGAP — Starting FastAPI Backend")
    logger.info("═" * 60)

    # Initialize Neo4j
    try:
        graph.initialize_graph()
        logger.info("  ✓ Neo4j connected")
    except Exception as e:
        logger.warning(f"  ✗ Neo4j not available: {e}")

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
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow the Next.js frontend to call us
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your frontend URL
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


# ═══════════════════════════════════════════════════════════
# Request/Response Models
# ═══════════════════════════════════════════════════════════

class AnalyzeRequest(BaseModel):
    idea: str


class ScanRequest(BaseModel):
    idea: str = ""
    keywords: str = ""
    tags: str = ""
    topics: str = ""


# ═══════════════════════════════════════════════════════════
# CogniGap API Endpoints (for Next.js frontend)
# ═══════════════════════════════════════════════════════════

@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    """
    Main CogniGap endpoint — the full pipeline:
    1. LLM Query Expansion
    2. Multi-domain search (ArXiv, Semantic Scholar, GitHub, Patents, etc.)
    3. Knowledge Graph ingestion
    4. GraphRAG reasoning
    5. Blindspot Matrix generation

    Returns the JSON expected by the CogniGap frontend.
    """
    idea = req.idea.strip()
    if not idea or len(idea) < 10:
        raise HTTPException(400, "Please provide a more detailed project description (at least 10 characters)")

    logger.info("═" * 60)
    logger.info("  COGNIGAP — Full Analysis Pipeline")
    logger.info("═" * 60)
    logger.info(f"  Idea: {idea[:100]}...")

    # Step 1: LLM Query Expansion
    expansion = expand_query(idea)
    queries = expansion.get("expanded_queries", [idea[:100]])

    # Step 2: Multi-domain search
    all_results = []

    # Use expanded queries for search
    for i, query in enumerate(queries[:3]):
        logger.info(f"  [{i+1}/{min(3, len(queries))}] Searching: '{query[:60]}...'")

        # Existing Indolance sources
        all_results.extend(scraper.search_semantic_scholar(query))
        rate_limit()
        all_results.extend(scraper.search_crossref(query))
        rate_limit()
        all_results.extend(scraper.search_openalex(query))
        rate_limit()
        all_results.extend(scraper.search_github(query))
        rate_limit()

        # New CogniGap sources
        all_results.extend(arxiv_searcher.search(query))
        rate_limit()
        all_results.extend(patent_searcher.search(query))
        rate_limit()

    # Deep GitHub search
    idea_keywords = [w for w in expansion.get("concepts", []) if " " not in w]
    github_deep = scraper.search_github_deep(idea, idea_keywords[:6])
    all_results.extend(github_deep)

    # Web search for the idea
    if len(idea) > 10:
        all_results.extend(scraper.search_web(idea[:150]))

    # Deduplicate
    all_results = scraper._deduplicate(all_results)
    all_results = [e for e in all_results if e.get("url")]

    logger.info(f"  Total search results: {len(all_results)}")

    # Step 3: GraphRAG Processing
    result = graphrag_engine.process(idea, all_results)

    # Also run the legacy comparison engine for enriched data
    try:
        scraper.global_trends = all_results
        scraper.save_trends()
        reader.scan_all()
    except Exception as e:
        logger.debug(f"  Legacy save failed: {e}")

    return result


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
# Legacy Indolance API Endpoints (backward compatibility)
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
    """Legacy: Run dual comparison analysis."""
    try:
        idea = req.idea
        kw_str = req.keywords
        tags_str = req.tags
        extra_keywords = [k.strip().lower() for k in kw_str.split(",") if k.strip()] if kw_str else []
        extra_tags = [t.strip().lower() for t in tags_str.split(",") if t.strip()] if tags_str else []
        all_keywords = list(set(extra_keywords + extra_tags))

        if not reader.knowledge_base:
            reader.load_knowledge_base()
        if not scraper.global_trends:
            scraper.load_trends()

        results = comparison_engine.analyze(reader, scraper, user_idea=idea, user_keywords=all_keywords)
        return {"success": True, "results": results}
    except Exception as e:
        raise HTTPException(500, str(e))


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
