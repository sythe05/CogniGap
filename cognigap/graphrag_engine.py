"""
CogniGap — GraphRAG Processing Engine
========================================
The core reasoning component. Combines Knowledge Graph (Neo4j) with
Vector Store (Qdrant) to perform multi-hop reasoning and subgraph extraction.

Instead of flat keyword or single-hop similarity matches, GraphRAG:
1. Uses LLM-expanded queries for semantic search across the vector store
2. Extracts relevant subgraphs from the knowledge graph
3. Computes concept-level overlap scores across papers, patents, and code
4. Identifies genuine gaps (uncharted territory)
"""

import hashlib
from datetime import datetime
from collections import Counter

from chronos.utils import logger, extract_words
from cognigap.config import PLAGIARISM_SOURCE_THRESHOLD
from cognigap import neo4j_graph as graph
from cognigap import vector_store as vs
from cognigap import query_expansion as qe


class GraphRAGEngine:
    """
    GraphRAG Processing Engine — performs multi-hop reasoning across
    the knowledge graph and vector store to assess project novelty.
    """

    def __init__(self):
        self.results = {}

    def process(self, idea_text, search_results):
        """
        Full GraphRAG pipeline:
        1. LLM Query Expansion
        2. Ingest search results into Knowledge Graph + Vector Store
        3. Multi-hop reasoning to compute concept overlaps
        4. Generate Blindspot Matrix data
        5. Compute originality score

        Args:
            idea_text: The user's informal project description
            search_results: List of dicts from global scraper (papers, repos, patents)

        Returns:
            dict matching the frontend's expected JSON schema
        """
        logger.info("═" * 60)
        logger.info("  COGNIGAP — GraphRAG Processing Engine — Starting")
        logger.info("═" * 60)

        # ── Step 1: LLM Query Expansion ──────────────────────────────
        expansion = qe.expand_query(idea_text)
        expanded_queries = expansion.get("expanded_queries", [])
        concepts = expansion.get("concepts", [])
        identified_gaps = expansion.get("gaps", [])

        logger.info(f"  Expanded into {len(expanded_queries)} queries, "
                    f"{len(concepts)} concepts")

        # ── Step 2: Ingest into Knowledge Graph ─────────────────────
        self._ingest_to_graph(idea_text, concepts, search_results)

        # ── Step 3: Ingest into Vector Store ────────────────────────
        self._ingest_to_vectors(search_results)

        # ── Step 4: Multi-hop Reasoning ─────────────────────────────
        concept_overlaps = self._compute_concept_overlaps(concepts, search_results)

        # ── Step 5: Find Overlapping Works ──────────────────────────
        overlaps = self._find_overlapping_works(concepts, search_results)

        # ── Step 6: Compute Originality Score ───────────────────────
        score = self._compute_originality_score(concept_overlaps, overlaps)
        assessment_confidence = self._assessment_confidence(search_results, overlaps)

        # ── Step 7: Find Gaps ───────────────────────────────────────
        gaps = self._compute_gaps(concepts, concept_overlaps, identified_gaps)

        # ── Build final result ──────────────────────────────────────
        self.results = {
            "expanded_queries": expanded_queries,
            "originality_score": score,
            "assessment_confidence": assessment_confidence,
            "evidence_count": len(search_results),
            "concepts": concept_overlaps,
            "overlaps": overlaps,
            "gaps": gaps,
            "baselines": None,
            "formal_summary": expansion.get("formal_summary", ""),
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(f"  Originality Score: {score}%")
        logger.info(f"  Concepts: {len(concept_overlaps)}")
        logger.info(f"  Overlapping Works: {len(overlaps)}")
        logger.info(f"  Gaps Found: {len(gaps)}")
        logger.info("═" * 60)

        return self.results

    # ═══════════════════════════════════════════════════════════
    # Internal Methods
    # ═══════════════════════════════════════════════════════════

    def _ingest_to_graph(self, idea_text, concepts, search_results):
        """Ingest all search results into the Neo4j knowledge graph."""
        logger.info("  ── Ingesting to Knowledge Graph ──")

        try:
            # Initialize graph
            graph.initialize_graph()

            # Save the project idea
            idea_id = hashlib.md5(idea_text.encode()).hexdigest()[:16]
            graph.save_project_idea(idea_id, idea_text)

            # Save concepts and link to idea
            for concept in concepts:
                graph.save_concept(concept)
                graph.link_idea_concept(idea_id, concept)

            # Categorize and save search results
            papers_saved = repos_saved = patents_saved = 0

            for item in search_results:
                source = item.get("source", "")
                keywords = item.get("keywords", [])

                try:
                    if source in ("semantic_scholar", "crossref", "openalex", "arxiv"):
                        item_id = graph.save_research_paper(item)
                        for kw in keywords[:10]:
                            if isinstance(kw, str):
                                graph.link_paper_keyword(item_id, kw)
                        # Link to matching concepts
                        for concept in concepts:
                            sim = self._concept_text_similarity(concept, item)
                            if sim > 0.1:
                                graph.link_paper_concept(item_id, concept, sim)
                        papers_saved += 1

                    elif source == "github":
                        item_id = graph.save_repository(item)
                        for kw in keywords[:10]:
                            if isinstance(kw, str):
                                graph.link_repository_keyword(item_id, kw)
                        for concept in concepts:
                            sim = self._concept_text_similarity(concept, item)
                            if sim > 0.1:
                                graph.link_repo_concept(item_id, concept, sim)
                        repos_saved += 1

                    elif source == "patent":
                        item_id = graph.save_patent(item)
                        for kw in keywords[:10]:
                            if isinstance(kw, str):
                                graph.link_patent_keyword(item_id, kw)
                        for concept in concepts:
                            sim = self._concept_text_similarity(concept, item)
                            if sim > 0.1:
                                graph.link_patent_concept(item_id, concept, sim)
                        patents_saved += 1
                except Exception as e:
                    logger.debug(f"  Failed to save item to graph: {e}")

            logger.info(f"  Saved: {papers_saved} papers, {repos_saved} repos, "
                       f"{patents_saved} patents")

        except Exception as e:
            logger.warning(f"  Graph ingestion failed (non-fatal): {e}")

    def _ingest_to_vectors(self, search_results):
        """Ingest search results into the Qdrant vector store."""
        logger.info("  ── Ingesting to Vector Store ──")

        try:
            documents = []
            for item in search_results:
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                text = f"{title} {snippet}"
                if len(text.strip()) < 10:
                    continue

                doc_id = hashlib.md5(text.encode()).hexdigest()
                documents.append({
                    "id": doc_id,
                    "text": text,
                    "metadata": {
                        "title": title,
                        "source": item.get("source", "unknown"),
                        "url": item.get("url", ""),
                        "year": item.get("year"),
                    }
                })

            if documents:
                vs.upsert_documents(documents)
                logger.info(f"  Vectorized {len(documents)} documents")
            else:
                logger.info("  No documents to vectorize")

        except Exception as e:
            logger.warning(f"  Vector ingestion failed (non-fatal): {e}")

    def _compute_concept_overlaps(self, concepts, search_results):
        """
        Compute per-concept overlap scores across papers, patents, and code.
        Use only this analysis run's results; Neo4j also contains records from
        previous analyses and cannot provide a query-scoped comparison here.
        """
        logger.info("  ── Computing Concept Overlaps ──")
        return self._text_based_concept_overlaps(concepts, search_results)

    def _text_based_concept_overlaps(self, concepts, search_results):
        """Compute concept overlaps using text similarity."""
        # Categorize results
        papers = [r for r in search_results
                  if r.get("source") in ("semantic_scholar", "crossref", "openalex", "arxiv")]
        patents = [r for r in search_results if r.get("source") == "patent"]
        repos = [r for r in search_results if r.get("source") == "github"]

        concept_data = []
        for concept in concepts:
            paper_sim = self._avg_concept_similarity(concept, papers) if papers else 0
            patent_sim = self._avg_concept_similarity(concept, patents) if patents else 0
            code_sim = self._avg_concept_similarity(concept, repos) if repos else 0

            concept_data.append({
                "name": concept,
                "papers": round(min(1.0, paper_sim), 2),
                "patents": round(min(1.0, patent_sim), 2),
                "code": round(min(1.0, code_sim), 2),
            })

        return concept_data

    def _find_overlapping_works(self, concepts, search_results):
        """Find current-run works that overlap with the project's concepts."""
        logger.info("  ── Finding Overlapping Works ──")
        overlaps = []
        for item in search_results:
            sim = self._item_overall_similarity(concepts, item)
            if sim >= PLAGIARISM_SOURCE_THRESHOLD:
                source = item.get("source", "unknown")
                # Map source to frontend categories
                if source in ("semantic_scholar", "crossref", "openalex", "arxiv"):
                    display_source = "arxiv"
                elif source == "github":
                    display_source = "github"
                elif source == "patent":
                    display_source = "patent"
                else:
                    display_source = "arxiv"

                matching_concepts = [
                    c for c in concepts
                    if self._concept_text_similarity(c, item) > 0.15
                ]

                overlaps.append({
                    "title": item.get("title", "Untitled"),
                    "source": display_source,
                    "url": item.get("url", "#"),
                    "similarity": round(sim, 2),
                    "concepts": matching_concepts,
                })

        overlaps.sort(key=lambda x: x["similarity"], reverse=True)
        return overlaps[:30]

    def _compute_originality_score(self, concept_overlaps, overlaps):
        """Estimate originality from positive matches; return None without evidence."""
        if not concept_overlaps or not overlaps:
            return None

        per_concept_matches = [
            max(
                float(concept.get("papers", 0)),
                float(concept.get("patents", 0)),
                float(concept.get("code", 0)),
            )
            for concept in concept_overlaps
        ]
        concept_match = sum(per_concept_matches) / len(per_concept_matches)

        strongest_matches = sorted(
            (float(item.get("similarity", 0)) for item in overlaps),
            reverse=True,
        )[:5]
        work_match = sum(strongest_matches) / len(strongest_matches)

        # An absent source is not evidence of originality. Compare the best
        # available source for each concept and the strongest current-run works.
        match_strength = 0.4 * concept_match + 0.6 * work_match
        return max(0, min(100, round((1 - match_strength) * 100)))

    @staticmethod
    def _assessment_confidence(search_results, overlaps):
        """Describe search evidence volume; this is not a calibrated probability."""
        source_count = len({
            item.get("source") for item in search_results if item.get("source")
        })
        if len(search_results) >= 20 and len(overlaps) >= 5 and source_count >= 3:
            return "high"
        if len(search_results) >= 5 and len(overlaps) >= 2 and source_count >= 2:
            return "medium"
        return "low"

    def _compute_gaps(self, concepts, concept_overlaps, llm_gaps):
        """Identify uncharted territory."""
        gaps = list(llm_gaps)  # Start with LLM-identified gaps

        # Add concepts with low overlap as gaps
        for concept_data in concept_overlaps:
            avg_overlap = (
                concept_data.get("papers", 0) +
                concept_data.get("patents", 0) +
                concept_data.get("code", 0)
            ) / 3
            if avg_overlap < 0.15:
                gap_text = f"'{concept_data['name']}' has very low coverage in existing literature"
                if gap_text not in gaps:
                    gaps.append(gap_text)

        return gaps[:8]

    # ═══════════════════════════════════════════════════════════
    # Similarity Helpers
    # ═══════════════════════════════════════════════════════════

    def _concept_text_similarity(self, concept, item):
        """Compute similarity between a concept and a search result item."""
        concept_lower = concept.lower()
        text = f"{item.get('title', '')} {item.get('snippet', '')}".lower()
        keywords = [k.lower() if isinstance(k, str) else "" for k in item.get("keywords", [])]

        # Direct match
        if concept_lower in text:
            return 0.8

        # Keyword overlap
        concept_words = set(extract_words(concept_lower))
        text_words = set(extract_words(text))
        keyword_set = set(keywords)

        if not concept_words:
            return 0

        overlap = concept_words & (text_words | keyword_set)
        return len(overlap) / len(concept_words) * 0.7

    def _avg_concept_similarity(self, concept, items):
        """Average similarity of a concept across a list of items."""
        if not items:
            return 0
        sims = [self._concept_text_similarity(concept, item) for item in items]
        # Use top-k average for more meaningful scores
        top_k = sorted(sims, reverse=True)[:min(5, len(sims))]
        return sum(top_k) / len(top_k) if top_k else 0

    def _item_overall_similarity(self, concepts, item):
        """Compute overall similarity of an item to the concept set."""
        if not concepts:
            return 0
        sims = [self._concept_text_similarity(c, item) for c in concepts]
        return max(sims) if sims else 0
