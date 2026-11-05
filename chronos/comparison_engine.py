"""
Project CogniGap — Part C: The Comparison Brain (The "Future")
==============================================================
Dual-score originality analysis: Local vs Global.
TF-IDF vectorization, cosine similarity, plagiarism source detection,
gap analysis, and project insights generation.
"""

import os, json
import numpy as np
from datetime import datetime
from collections import Counter

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import (
    LOCAL_SIMILARITY_HIGH, LOCAL_SIMILARITY_MEDIUM,
    GLOBAL_SIMILARITY_HIGH, GLOBAL_SIMILARITY_MEDIUM,
    PLAGIARISM_SOURCE_THRESHOLD, TOP_GAP_SUGGESTIONS,
    DATA_DIR, STATIC_IMG_DIR
)
from chronos.utils import logger, extract_words


class ComparisonEngine:
    def __init__(self):
        self.results = {}

    def analyze(self, local_reader, global_scraper, user_idea="", user_keywords=None):
        logger.info("=" * 60)
        logger.info("  COGNIGAP — Part C: Comparison Brain — Analyzing")
        logger.info("=" * 60)

        user_keywords = user_keywords or []
        user_text = user_idea
        if user_keywords:
            user_text += " " + " ".join(user_keywords)

        if not user_text.strip():
            logger.warning("  No user idea provided.")
            self.results = self._empty_results()
            return self.results

        # ── LOCAL ANALYSIS ───────────────────────────────────────────
        local_result = self._analyze_local(user_text, local_reader)

        # ── GLOBAL ANALYSIS ──────────────────────────────────────────
        global_result = self._analyze_global(user_text, user_keywords, global_scraper)

        # ── GAP ANALYSIS ─────────────────────────────────────────────
        local_kw = set(k.lower() for k in user_keywords) if user_keywords else set()
        local_kw.update(extract_words(user_idea))
        global_kw_freq = global_scraper.get_keyword_frequencies()
        gaps = self._find_gaps(local_kw, global_kw_freq)

        # ── INSIGHTS ─────────────────────────────────────────────────
        insights = self._generate_insights(
            user_idea, user_keywords,
            local_result, global_result,
            global_scraper.global_trends, gaps
        )

        # ── REFERENCE MATERIALS ──────────────────────────────────────
        references = self._extract_references(global_scraper.global_trends, global_result)

        # ── CONNECTION MAP ───────────────────────────────────────────
        global_kw_set = set(k for k, _ in global_kw_freq)
        overlap = local_kw & global_kw_set
        only_local = local_kw - global_kw_set
        only_global = global_kw_set - local_kw
        map_path = self._generate_connection_map(local_kw, global_kw_freq)

        self.results = {
            "timestamp": datetime.now().isoformat(),
            "local_originality_score": local_result["score"],
            "global_originality_score": global_result["score"],
            "local_plagiarism_pct": round(100 - local_result["score"], 1),
            "global_plagiarism_pct": round(100 - global_result["score"], 1),
            "local_max_similarity": local_result["max_sim"],
            "local_avg_similarity": local_result["avg_sim"],
            "local_similar_files": local_result["similar_files"],
            "local_file_count": local_result["file_count"],
            "global_max_similarity": global_result["max_sim"],
            "global_avg_similarity": global_result["avg_sim"],
            "global_similar_items": global_result["similar_items"][:20],
            "global_result_count": global_result["result_count"],
            "plagiarism_sources": global_result["plagiarism_sources"],
            "total_user_keywords": len(local_kw),
            "total_global_keywords": len(global_kw_set),
            "overlap_count": len(overlap),
            "overlap_keywords": sorted(overlap)[:20],
            "only_local": sorted(only_local)[:20],
            "only_global": sorted(only_global)[:20],
            "gaps": gaps,
            "connection_map": map_path,
            "status_counts": global_result["status_counts"],
            "source_breakdown": global_result["source_breakdown"],
            "insights": insights,
            "references": references,
        }

        self.save_results()
        logger.info(f"  Local Originality:  {local_result['score']}%")
        logger.info(f"  Global Originality: {global_result['score']}%")
        logger.info(f"  Plagiarism Sources: {len(global_result['plagiarism_sources'])}")
        logger.info(f"  Insights generated: {len(insights.get('pros', []))} pros, {len(insights.get('cons', []))} cons")
        logger.info("=" * 60)
        return self.results

    # ── LOCAL ────────────────────────────────────────────────────────
    def _analyze_local(self, user_text, local_reader):
        logger.info("  ── Local Analysis ──")
        if not local_reader.knowledge_base:
            local_reader.load_knowledge_base()
        if not local_reader.knowledge_base:
            logger.info("    No local files found. Local score = 100%.")
            return {"score": 100.0, "max_sim": 0, "avg_sim": 0, "similar_files": [], "file_count": 0}

        local_docs = []
        for entry in local_reader.knowledge_base:
            kw_text = " ".join(kw["keyword"] for kw in entry.get("keywords", []))
            snippet = entry.get("snippet", "")
            local_docs.append(f"{kw_text} {snippet}")

        if not local_docs:
            return {"score": 100.0, "max_sim": 0, "avg_sim": 0, "similar_files": [], "file_count": 0}

        all_docs = [user_text] + local_docs
        try:
            vectorizer = TfidfVectorizer(max_features=500, stop_words='english', ngram_range=(1, 2), min_df=1)
            tfidf_matrix = vectorizer.fit_transform(all_docs)
        except ValueError:
            return {"score": 100.0, "max_sim": 0, "avg_sim": 0, "similar_files": [], "file_count": 0}

        similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
        similar_files = []
        for i, sim in enumerate(similarities):
            if i < len(local_reader.knowledge_base):
                entry = local_reader.knowledge_base[i]
                status = "Heavily Overlapping" if sim >= LOCAL_SIMILARITY_HIGH else \
                         "Some Overlap" if sim >= LOCAL_SIMILARITY_MEDIUM else "Original"
                similar_files.append({
                    "filename": entry.get("filename", ""), "source_file": entry.get("source_file", ""),
                    "similarity": round(float(sim), 4), "status": status,
                    "snippet": entry.get("snippet", "")[:200],
                })
        similar_files.sort(key=lambda x: x["similarity"], reverse=True)
        max_sim = float(np.max(similarities)) if len(similarities) > 0 else 0
        avg_sim = float(np.mean(similarities)) if len(similarities) > 0 else 0
        if len(similarities) > 0 and max_sim > 0:
            effective_local = 0.6 * max_sim + 0.4 * avg_sim
            overlap_pct = min(95.0, (effective_local / 0.35) * 80.0)
            score = round(max(5.0, 100.0 - overlap_pct), 1)
        else:
            score = 100.0
        logger.info(f"    Compared against {len(local_docs)} files, score={score}%")
        return {"score": score, "max_sim": round(max_sim, 4), "avg_sim": round(avg_sim, 4),
                "similar_files": similar_files[:10], "file_count": len(local_docs)}

    # ── GLOBAL ───────────────────────────────────────────────────────
    def _analyze_global(self, user_text, user_keywords, global_scraper):
        logger.info("  ── Global Analysis ──")
        if not global_scraper.global_trends:
            global_scraper.load_trends()
        if not global_scraper.global_trends:
            logger.info("    No global data. Global score = 100%.")
            return self._empty_global()

        global_docs = global_scraper.get_combined_documents()
        if not global_docs:
            return self._empty_global()

        all_docs = [user_text] + global_docs
        try:
            vectorizer = TfidfVectorizer(max_features=800, stop_words='english', ngram_range=(1, 2), min_df=1)
            tfidf_matrix = vectorizer.fit_transform(all_docs)
        except ValueError:
            return self._empty_global()

        similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
        similar_items = []
        plagiarism_sources = []
        source_counter = Counter()

        for i, sim in enumerate(similarities):
            if i < len(global_scraper.global_trends):
                entry = global_scraper.global_trends[i].copy()
                entry["similarity"] = round(float(sim), 4)
                if sim >= GLOBAL_SIMILARITY_HIGH:
                    entry["status"] = "Already Exists"
                elif sim >= GLOBAL_SIMILARITY_MEDIUM:
                    entry["status"] = "Similar Work Found"
                else:
                    entry["status"] = "Potentially Original"
                similar_items.append(entry)
                source_counter[entry.get("source", "unknown")] += 1

                if sim >= PLAGIARISM_SOURCE_THRESHOLD:
                    plagiarism_sources.append({
                        "title": entry.get("title", "Untitled"),
                        "url": entry.get("url", ""),
                        "similarity_pct": round(float(sim) * 100, 1),
                        "source_type": entry.get("source", "unknown"),
                        "source_label": entry.get("source_label", "Unknown"),
                        "year": entry.get("year"),
                        "citations": entry.get("citations", 0),
                        "stars": entry.get("stars", 0),
                        "snippet": entry.get("snippet", "")[:250],
                    })

        similar_items.sort(key=lambda x: x["similarity"], reverse=True)
        plagiarism_sources.sort(key=lambda x: x["similarity_pct"], reverse=True)
        max_sim = float(np.max(similarities)) if len(similarities) > 0 else 0
        top_sims = sorted(similarities, reverse=True)[:min(10, len(similarities))]
        weighted_avg = float(np.mean(top_sims)) if top_sims else 0
        # Calibrated text novelty scale: in TF-IDF cosine similarity, 0.35+ represents near-identical projects
        if top_sims and max_sim > 0:
            effective_match = 0.45 * max_sim + 0.55 * weighted_avg
            base_overlap = min(92.0, (effective_match / 0.35) * 80.0)
            crowd_penalty = min(15.0, len(plagiarism_sources) * 1.2)
            total_overlap = min(96.0, max(4.0, base_overlap + crowd_penalty))
            score = round(100.0 - total_overlap, 1)
        else:
            score = 100.0

        status_counts = {
            "already_exists": sum(1 for i in similar_items if i["status"] == "Already Exists"),
            "similar_work": sum(1 for i in similar_items if i["status"] == "Similar Work Found"),
            "original": sum(1 for i in similar_items if i["status"] == "Potentially Original"),
        }
        logger.info(f"    Compared against {len(global_docs)} results, score={score}%")
        logger.info(f"    Plagiarism sources found: {len(plagiarism_sources)}")
        return {"score": score, "max_sim": round(max_sim, 4), "avg_sim": round(float(np.mean(similarities)), 4),
                "similar_items": similar_items, "plagiarism_sources": plagiarism_sources[:25],
                "result_count": len(global_docs), "status_counts": status_counts,
                "source_breakdown": dict(source_counter)}

    def _empty_global(self):
        return {"score": 100.0, "max_sim": 0, "avg_sim": 0, "similar_items": [],
                "plagiarism_sources": [], "result_count": 0,
                "status_counts": {"already_exists": 0, "similar_work": 0, "original": 0},
                "source_breakdown": {}}

    # ── INSIGHTS GENERATOR ───────────────────────────────────────────
    def _generate_insights(self, user_idea, user_keywords, local_result, global_result, trends, gaps):
        """Generate structured project insights based on analysis data."""
        logger.info("  ── Generating Insights ──")

        g_score = global_result["score"]
        l_score = local_result["score"]
        plag_sources = global_result.get("plagiarism_sources", [])
        similar_items = global_result.get("similar_items", [])

        # ── VERDICT ──────────────────────────────────────────────────
        if g_score >= 85:
            verdict = "Highly Original"
            verdict_detail = "Your idea is quite unique. Very few existing projects closely match your concept."
            should_build = True
        elif g_score >= 65:
            verdict = "Moderately Original"
            verdict_detail = "Your idea has some overlap with existing work, but there's enough uniqueness to differentiate."
            should_build = True
        elif g_score >= 45:
            verdict = "Partially Original"
            verdict_detail = "Significant similar work exists. You'll need a strong differentiator to stand out."
            should_build = True
        else:
            verdict = "Low Originality"
            verdict_detail = "This concept already exists in multiple forms. Consider pivoting or finding a unique angle."
            should_build = False

        # ── PROS ─────────────────────────────────────────────────────
        pros = []

        if g_score >= 70:
            pros.append({
                "title": "High Originality",
                "detail": f"With a {g_score}% global originality score, your idea stands out from existing work.",
                "icon": "✨"
            })

        # Check if there's research backing (similar papers = validated field)
        academic_count = sum(1 for s in plag_sources if s.get("source_type") in ("semantic_scholar", "crossref", "openalex"))
        if academic_count > 0:
            pros.append({
                "title": "Research-Backed Field",
                "detail": f"Found {academic_count} related academic papers. This means the field is active and your work would be relevant to ongoing research.",
                "icon": "📚"
            })

        # Check gaps — unique keywords = competitive advantage
        if gaps and len(gaps) >= 3:
            pros.append({
                "title": "Room for Innovation",
                "detail": f"Found {len(gaps)} trending topics not yet covered in your domain. These represent opportunities for unique contributions.",
                "icon": "💡"
            })

        # Check GitHub presence
        github_items = [s for s in similar_items if s.get("source") == "github"]
        github_high = [g for g in github_items if g.get("similarity", 0) >= 0.3]
        if github_items and not github_high:
            pros.append({
                "title": "No Direct GitHub Competitor",
                "detail": "While related repos exist, none closely match your specific approach. You'd be filling a gap in open-source.",
                "icon": "🚀"
            })

        # High-citation related work = proven demand
        high_cite = [s for s in plag_sources if (s.get("citations") or 0) > 50]
        if high_cite:
            pros.append({
                "title": "Proven Demand",
                "detail": f"Related papers have {high_cite[0]['citations']}+ citations, indicating strong interest in this area.",
                "icon": "📈"
            })

        if l_score >= 90:
            pros.append({
                "title": "Fresh Perspective",
                "detail": "Your idea is very different from your existing work, showing you're exploring new territory.",
                "icon": "🔬"
            })

        # ── CONS ─────────────────────────────────────────────────────
        cons = []

        if g_score < 50:
            cons.append({
                "title": "Highly Saturated Area",
                "detail": f"With only {g_score}% originality, many similar projects already exist. Differentiation will be challenging.",
                "icon": "⚠️"
            })

        existing_count = global_result.get("status_counts", {}).get("already_exists", 0)
        if existing_count > 3:
            top_existing = [s for s in similar_items if s.get("status") == "Already Exists"][:3]
            names = ", ".join(s.get("title", "")[:40] for s in top_existing)
            cons.append({
                "title": f"{existing_count} Nearly Identical Projects Found",
                "detail": f"Projects like {names} closely match your concept.",
                "icon": "🔴"
            })

        # Popular GitHub repos = strong competition
        popular_repos = [g for g in github_items if (g.get("stars") or 0) > 100]
        if popular_repos:
            top = popular_repos[0]
            cons.append({
                "title": "Established Open-Source Competition",
                "detail": f"'{top.get('title', '')}' has {top.get('stars', 0)} stars on GitHub. You'd need significant improvements to compete.",
                "icon": "⭐"
            })

        if len(plag_sources) > 15:
            cons.append({
                "title": "Extensive Existing Literature",
                "detail": f"Found {len(plag_sources)} matching sources. The concept is well-explored in academic and industry work.",
                "icon": "📄"
            })

        if g_score >= 50 and g_score < 70:
            cons.append({
                "title": "Moderate Risk of Overlap",
                "detail": "Some similar projects exist. Make sure to clearly define what makes your approach unique.",
                "icon": "⚡"
            })

        # ── USEFULNESS ASSESSMENT ────────────────────────────────────
        usefulness = self._assess_usefulness(user_idea, user_keywords, plag_sources, github_items, g_score)

        # ── RECOMMENDATION ───────────────────────────────────────────
        if should_build and g_score >= 65:
            recommendation = "✅ GO AHEAD — This project is worth building."
            rec_detail = "Your idea is original enough to stand on its own. Focus on the unique aspects and build an MVP."
        elif should_build:
            recommendation = "🟡 PROCEED WITH CAUTION — Differentiation needed."
            rec_detail = "The core concept exists, but you can still succeed by focusing on a unique angle, better UX, or an underserved niche."
        else:
            recommendation = "🔴 CONSIDER PIVOTING — Heavy competition exists."
            rec_detail = "This exact idea is well-covered. Consider a different approach, combining it with another concept, or targeting a specific niche."

        return {
            "verdict": verdict,
            "verdict_detail": verdict_detail,
            "should_build": should_build,
            "recommendation": recommendation,
            "recommendation_detail": rec_detail,
            "pros": pros,
            "cons": cons,
            "usefulness": usefulness,
        }

    def _assess_usefulness(self, idea, keywords, plag_sources, github_items, g_score):
        """Assess real-world usefulness of the project."""
        # Categorize the project domain
        idea_lower = (idea or "").lower()
        kw_lower = " ".join(keywords or []).lower()
        combined = f"{idea_lower} {kw_lower}"

        scores = {}

        # Real-world impact
        impact_keywords = ["health", "medical", "safety", "security", "education", "environment",
                          "energy", "water", "food", "disaster", "emergency", "accessibility"]
        impact_hits = sum(1 for k in impact_keywords if k in combined)
        scores["real_world_impact"] = min(10, 4 + impact_hits * 2)

        # Technical innovation
        tech_keywords = ["machine learning", "ai", "blockchain", "quantum", "iot",
                        "neural", "deep learning", "edge computing", "5g"]
        tech_hits = sum(1 for k in tech_keywords if k in combined)
        scores["technical_innovation"] = min(10, 3 + tech_hits * 2 + (1 if g_score > 70 else 0))

        # Market potential
        market_keywords = ["automation", "platform", "saas", "app", "mobile", "web",
                          "e-commerce", "fintech", "marketplace"]
        market_hits = sum(1 for k in market_keywords if k in combined)
        # High competition = proven market, but harder entry
        if g_score < 50:
            scores["market_potential"] = min(10, 5 + market_hits)  # Proven market
        else:
            scores["market_potential"] = min(10, 3 + market_hits + 1)

        # Learning value
        scores["learning_value"] = min(10, 6 + tech_hits)

        # Community interest (based on citations/stars found)
        total_citations = sum(s.get("citations", 0) for s in plag_sources[:10])
        total_stars = sum(g.get("stars", 0) for g in github_items[:5])
        if total_citations > 500 or total_stars > 5000:
            scores["community_interest"] = 9
        elif total_citations > 100 or total_stars > 500:
            scores["community_interest"] = 7
        elif total_citations > 10 or total_stars > 50:
            scores["community_interest"] = 5
        else:
            scores["community_interest"] = 4

        overall = round(sum(scores.values()) / len(scores), 1)
        scores["overall"] = overall

        return scores

    def _extract_references(self, trends, global_result):
        """Extract the best reference materials for the user."""
        refs = {"papers": [], "repos": [], "web": []}

        # Get top-cited papers
        papers = [t for t in trends if t.get("source") in ("semantic_scholar", "crossref", "openalex")]
        papers.sort(key=lambda x: x.get("citations", 0), reverse=True)
        for p in papers[:8]:
            if p.get("url"):
                refs["papers"].append({
                    "title": p.get("title", ""),
                    "url": p.get("url", ""),
                    "year": p.get("year"),
                    "citations": p.get("citations", 0),
                    "source": p.get("source_label", "Paper"),
                })

        # Get top GitHub repos
        repos = [t for t in trends if t.get("source") == "github"]
        repos.sort(key=lambda x: x.get("stars", 0), reverse=True)
        for r in repos[:8]:
            if r.get("url"):
                refs["repos"].append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "stars": r.get("stars", 0),
                    "language": r.get("language", ""),
                    "snippet": r.get("snippet", "")[:150],
                })

        # Get web results
        web = [t for t in trends if t.get("source") == "web"]
        for w in web[:6]:
            if w.get("url"):
                refs["web"].append({
                    "title": w.get("title", ""),
                    "url": w.get("url", ""),
                    "snippet": w.get("snippet", "")[:150],
                })

        return refs

    # ── GAP ANALYSIS ─────────────────────────────────────────────────
    def _find_gaps(self, local_kw, global_kw_freq):
        gaps = []
        for keyword, freq in global_kw_freq:
            if keyword.lower() not in local_kw:
                gaps.append({
                    "keyword": keyword, "global_frequency": freq,
                    "trending_score": round(freq / max(1, global_kw_freq[0][1]) * 100, 1),
                    "suggestion": f"Consider exploring '{keyword}' — trending globally but missing from your work."
                })
        return gaps[:TOP_GAP_SUGGESTIONS]

    # ── CONNECTION MAP ───────────────────────────────────────────────
    def _generate_connection_map(self, local_kw, global_kw_freq):
        try:
            fig, ax = plt.subplots(1, 1, figsize=(12, 8))
            fig.patch.set_facecolor('#111111')
            ax.set_facecolor('#111111')
            local_list = sorted(local_kw)[:12]
            global_list = [k for k, _ in global_kw_freq[:12]]
            if not local_list and not global_list:
                plt.close(fig)
                return ""
            local_positions = {}
            for i, kw in enumerate(local_list):
                y = 1 - (i / max(len(local_list) - 1, 1))
                local_positions[kw] = (0.2, y)
            global_positions = {}
            for i, kw in enumerate(global_list):
                y = 1 - (i / max(len(global_list) - 1, 1))
                global_positions[kw] = (0.8, y)
            for lkw, (lx, ly) in local_positions.items():
                for gkw, (gx, gy) in global_positions.items():
                    if lkw == gkw.lower() or gkw == lkw.lower():
                        ax.plot([lx, gx], [ly, gy], color='#999999', alpha=0.5, linewidth=1.5)
                    else:
                        ax.plot([lx, gx], [ly, gy], color='#222222', alpha=0.2, linewidth=0.3)
            for kw, (x, y) in local_positions.items():
                ax.scatter(x, y, s=180, c='#888888', zorder=5, edgecolors='#111111', linewidth=2)
                ax.text(x - 0.02, y, kw, ha='right', va='center', fontsize=8, color='#c8c8c8', fontweight='bold')
            for kw, (x, y) in global_positions.items():
                ax.scatter(x, y, s=180, c='#555555', zorder=5, edgecolors='#111111', linewidth=2)
                ax.text(x + 0.02, y, kw, ha='left', va='center', fontsize=8, color='#c8c8c8', fontweight='bold')
            ax.text(0.2, 1.08, 'YOUR KEYWORDS', ha='center', fontsize=12, color='#aaaaaa', fontweight='bold')
            ax.text(0.8, 1.08, 'GLOBAL TRENDS', ha='center', fontsize=12, color='#777777', fontweight='bold')
            ax.set_xlim(-0.1, 1.1); ax.set_ylim(-0.1, 1.15); ax.axis('off')
            ax.set_title('Project CogniGap — Connection Map', color='#c8c8c8', fontsize=16, fontweight='bold', pad=20)
            path = os.path.join(STATIC_IMG_DIR, "connection_map.png")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            fig.savefig(path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor(), edgecolor='none')
            plt.close(fig)
            return "img/connection_map.png"
        except Exception as e:
            logger.error(f"  Map generation failed: {e}")
            return ""

    def _empty_results(self):
        return {
            "timestamp": datetime.now().isoformat(),
            "local_originality_score": 0, "global_originality_score": 0,
            "local_plagiarism_pct": 0, "global_plagiarism_pct": 0,
            "local_max_similarity": 0, "local_avg_similarity": 0,
            "local_similar_files": [], "local_file_count": 0,
            "global_max_similarity": 0, "global_avg_similarity": 0,
            "global_similar_items": [], "global_result_count": 0,
            "plagiarism_sources": [],
            "total_user_keywords": 0, "total_global_keywords": 0,
            "overlap_count": 0, "overlap_keywords": [],
            "only_local": [], "only_global": [],
            "gaps": [], "connection_map": "",
            "status_counts": {"already_exists": 0, "similar_work": 0, "original": 0},
            "source_breakdown": {},
            "insights": {"verdict": "", "pros": [], "cons": [], "usefulness": {},
                         "recommendation": "", "should_build": False},
            "references": {"papers": [], "repos": [], "web": []},
        }

    def save_results(self):
        p = os.path.join(DATA_DIR, "analysis_results.json")
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, default=str)
        logger.info(f"  Results saved to: {p}")

    def load_results(self):
        p = os.path.join(DATA_DIR, "analysis_results.json")
        if os.path.exists(p):
            with open(p, 'r', encoding='utf-8') as f:
                self.results = json.load(f)
                return self.results
        return None
