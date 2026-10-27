"""
Project CogniGap — Part B: The Global Searcher (The "Present")
==============================================================
API-based search across academic databases, code repositories, and the web.
Uses free, reliable APIs. Validates all URLs before returning.
"""

import os, re, json, time, random
from datetime import datetime
from urllib.parse import quote_plus
import requests
from collections import Counter

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import (
    SEMANTIC_SCHOLAR_API, SEMANTIC_SCHOLAR_FIELDS, SEMANTIC_SCHOLAR_LIMIT,
    CROSSREF_API, CROSSREF_LIMIT,
    GITHUB_SEARCH_API, GITHUB_LIMIT, GITHUB_TOKEN,
    OPENALEX_API, OPENALEX_LIMIT,
    API_DELAY_MIN, API_DELAY_MAX, API_USER_AGENT, DATA_DIR
)
from chronos.utils import logger, extract_words


class GlobalScraper:
    def __init__(self, topics=None):
        self.topics = topics or []
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": API_USER_AGENT, "Accept": "application/json"})
        self.global_trends = []

    def _rate_limit(self, extra=0):
        time.sleep(random.uniform(API_DELAY_MIN, API_DELAY_MAX) + extra)

    def _validate_url(self, url):
        """Ensure URL is well-formed and has a scheme."""
        if not url or not isinstance(url, str):
            return ""
        url = url.strip()
        if not url.startswith("http"):
            if url.startswith("//"):
                url = "https:" + url
            elif "doi.org" in url or "10." in url:
                # It's a bare DOI
                doi = url.replace("https://doi.org/", "").replace("http://doi.org/", "")
                url = f"https://doi.org/{doi}"
            else:
                return ""
        return url

    # ── Semantic Scholar API ─────────────────────────────────────────────
    def search_semantic_scholar(self, query, limit=None):
        limit = limit or SEMANTIC_SCHOLAR_LIMIT
        results = []
        logger.info(f"  [Semantic Scholar] Searching: '{query}'")
        try:
            resp = self.session.get(SEMANTIC_SCHOLAR_API, params={
                "query": query, "limit": limit, "fields": SEMANTIC_SCHOLAR_FIELDS
            }, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            for paper in data.get("data", []):
                title = paper.get("title", "")
                if not title:
                    continue
                abstract = paper.get("abstract", "") or ""
                paper_id = paper.get("paperId", "")
                ext_ids = paper.get("externalIds", {}) or {}

                # Build the best available URL
                url = ""
                if ext_ids.get("DOI"):
                    url = f"https://doi.org/{ext_ids['DOI']}"
                elif ext_ids.get("ArXiv"):
                    url = f"https://arxiv.org/abs/{ext_ids['ArXiv']}"
                elif paper_id:
                    url = f"https://www.semanticscholar.org/paper/{paper_id}"

                url = self._validate_url(url)
                results.append({
                    "title": title, "snippet": abstract[:500], "url": url,
                    "year": paper.get("year"), "citations": paper.get("citationCount", 0),
                    "source": "semantic_scholar", "source_label": "Academic Paper",
                    "query": query, "keywords": extract_words(f"{title} {abstract}")[:15],
                    "scraped_at": datetime.now().isoformat()
                })
            logger.info(f"    Found {len(results)} papers")
        except Exception as ex:
            logger.error(f"    Semantic Scholar failed: {ex}")
        return results

    # ── CrossRef API ─────────────────────────────────────────────────────
    def search_crossref(self, query, limit=None):
        limit = limit or CROSSREF_LIMIT
        results = []
        logger.info(f"  [CrossRef] Searching: '{query}'")
        try:
            resp = self.session.get(CROSSREF_API, params={
                "query": query, "rows": limit,
                "select": "DOI,title,abstract,published-print,is-referenced-by-count,URL,subject"
            }, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            for item in data.get("message", {}).get("items", []):
                title_list = item.get("title", [])
                title = title_list[0] if title_list else ""
                if not title:
                    continue
                abstract = re.sub(r'<[^>]+>', '', item.get("abstract", "") or "")
                doi = item.get("DOI", "")
                url = f"https://doi.org/{doi}" if doi else ""
                url = self._validate_url(url)
                pub_date = item.get("published-print", {}) or item.get("published-online", {}) or {}
                date_parts = pub_date.get("date-parts", [[None]])
                year = date_parts[0][0] if date_parts and date_parts[0] else None
                results.append({
                    "title": title, "snippet": abstract[:500], "url": url, "year": year,
                    "citations": item.get("is-referenced-by-count", 0),
                    "source": "crossref", "source_label": "Published Work",
                    "query": query, "keywords": extract_words(f"{title} {abstract}")[:15],
                    "scraped_at": datetime.now().isoformat()
                })
            logger.info(f"    Found {len(results)} works")
        except Exception as ex:
            logger.error(f"    CrossRef failed: {ex}")
        return results

    # ── OpenAlex API ─────────────────────────────────────────────────────
    def search_openalex(self, query, limit=None):
        limit = limit or OPENALEX_LIMIT
        results = []
        logger.info(f"  [OpenAlex] Searching: '{query}'")
        try:
            resp = self.session.get(OPENALEX_API, params={
                "search": query, "per_page": limit, "mailto": "student@example.com"
            }, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            for work in data.get("results", []):
                title = work.get("title", "") or ""
                if not title:
                    continue
                abstract = ""
                inv_abstract = work.get("abstract_inverted_index")
                if inv_abstract:
                    word_positions = []
                    for word, positions in inv_abstract.items():
                        for pos in positions:
                            word_positions.append((pos, word))
                    word_positions.sort()
                    abstract = " ".join(w for _, w in word_positions)

                doi = work.get("doi", "") or ""
                url = self._validate_url(doi) if doi else ""
                if not url:
                    # Use the OpenAlex landing page
                    oa_id = work.get("id", "")
                    if oa_id:
                        url = oa_id  # OpenAlex IDs are valid URLs

                url = self._validate_url(url)
                results.append({
                    "title": title, "snippet": abstract[:500], "url": url,
                    "year": work.get("publication_year"),
                    "citations": work.get("cited_by_count", 0),
                    "source": "openalex", "source_label": "Academic Paper",
                    "query": query, "keywords": extract_words(f"{title} {abstract}")[:15],
                    "scraped_at": datetime.now().isoformat()
                })
            logger.info(f"    Found {len(results)} works")
        except Exception as ex:
            logger.error(f"    OpenAlex failed: {ex}")
        return results

    # ── GitHub Search API — Deep Search ──────────────────────────────────
    def search_github(self, query, limit=None):
        """Search GitHub repos by query. Returns richer results with README fetching."""
        limit = limit or GITHUB_LIMIT
        results = []
        logger.info(f"  [GitHub] Searching: '{query}'")
        headers = {"Accept": "application/vnd.github.v3+json"}
        if GITHUB_TOKEN:
            headers["Authorization"] = f"token {GITHUB_TOKEN}"

        try:
            resp = self.session.get(GITHUB_SEARCH_API, params={
                "q": query, "sort": "stars", "order": "desc", "per_page": limit
            }, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            for repo in data.get("items", []):
                title = repo.get("full_name", "")
                if not title:
                    continue
                description = repo.get("description", "") or ""
                url = repo.get("html_url", "")
                language = repo.get("language", "") or ""
                created = repo.get("created_at", "")
                year = int(created[:4]) if created else None
                topics = repo.get("topics", []) or []

                # Build richer text for matching
                topics_text = " ".join(topics) if topics else ""
                full_text = f"{title} {description} {language} {topics_text}"

                results.append({
                    "title": title, "snippet": description[:500], "url": url,
                    "year": year, "stars": repo.get("stargazers_count", 0),
                    "forks": repo.get("forks_count", 0),
                    "language": language, "topics": topics,
                    "source": "github", "source_label": "GitHub Repository",
                    "query": query,
                    "keywords": extract_words(full_text)[:15],
                    "scraped_at": datetime.now().isoformat()
                })
            logger.info(f"    Found {len(results)} repositories")
        except Exception as ex:
            logger.error(f"    GitHub Search failed: {ex}")
        return results

    def search_github_deep(self, idea_text, keywords):
        """Run multiple targeted GitHub searches for more thorough matching."""
        all_results = []

        # Search 1: Full idea text (truncated)
        if idea_text and len(idea_text) > 10:
            short_idea = idea_text[:128].strip()
            all_results.extend(self.search_github(short_idea, limit=10))
            self._rate_limit(extra=1)

        # Search 2: Each keyword pair combination
        if keywords and len(keywords) >= 2:
            # Search pairs of keywords for more specific results
            for i in range(0, min(len(keywords), 6), 2):
                pair = " ".join(keywords[i:i+2])
                all_results.extend(self.search_github(pair, limit=8))
                self._rate_limit(extra=1)

        # Search 3: "in:readme" search for deeper matching
        if keywords:
            readme_query = " ".join(keywords[:4]) + " in:readme"
            logger.info(f"  [GitHub] Deep search in READMEs...")
            all_results.extend(self.search_github(readme_query, limit=10))
            self._rate_limit(extra=1)

        # Search 4: topic-based search
        if keywords:
            topic_query = " ".join(f"topic:{kw}" for kw in keywords[:3] if " " not in kw)
            if topic_query:
                logger.info(f"  [GitHub] Topic search: {topic_query}")
                all_results.extend(self.search_github(topic_query, limit=10))

        return all_results

    # ── DuckDuckGo Instant Answer API ────────────────────────────────────
    def search_web(self, query):
        """Use DuckDuckGo HTML search for general web results."""
        results = []
        logger.info(f"  [Web Search] Searching: '{query}'")
        try:
            # DuckDuckGo HTML lite version
            resp = self.session.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                timeout=15
            )
            resp.raise_for_status()

            # Parse HTML results
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "lxml")
            for result in soup.select(".result")[:10]:
                title_el = result.select_one(".result__a")
                snippet_el = result.select_one(".result__snippet")
                if not title_el:
                    continue

                title = title_el.get_text(strip=True)
                url_raw = title_el.get("href", "")
                snippet = snippet_el.get_text(strip=True) if snippet_el else ""

                # DuckDuckGo wraps URLs in a redirect; extract the real URL
                if "uddg=" in url_raw:
                    from urllib.parse import unquote, urlparse, parse_qs
                    parsed = urlparse(url_raw)
                    qs = parse_qs(parsed.query)
                    url = unquote(qs.get("uddg", [url_raw])[0])
                else:
                    url = url_raw

                url = self._validate_url(url)
                if not url or not title:
                    continue

                results.append({
                    "title": title, "snippet": snippet[:500], "url": url,
                    "year": None, "source": "web", "source_label": "Web Result",
                    "query": query, "keywords": extract_words(f"{title} {snippet}")[:15],
                    "scraped_at": datetime.now().isoformat()
                })

            logger.info(f"    Found {len(results)} web results")
        except Exception as ex:
            logger.error(f"    Web search failed: {ex}")
        return results

    # ── Full Pipeline ────────────────────────────────────────────────────
    def scrape_all(self, idea_text="", idea_keywords=None):
        logger.info("=" * 60)
        logger.info("  COGNIGAP — Part B: Global Searcher — Starting")
        logger.info("=" * 60)
        self.global_trends = []
        idea_keywords = idea_keywords or []

        for i, topic in enumerate(self.topics, 1):
            logger.info(f"  [{i}/{len(self.topics)}] Topic: {topic}")

            # Academic sources
            self.global_trends.extend(self.search_semantic_scholar(topic))
            self._rate_limit()
            self.global_trends.extend(self.search_crossref(topic))
            self._rate_limit()
            self.global_trends.extend(self.search_openalex(topic))
            self._rate_limit()

            # Standard GitHub search per topic
            self.global_trends.extend(self.search_github(topic))
            self._rate_limit()

            # Web search per topic
            self.global_trends.extend(self.search_web(topic))
            if i < len(self.topics):
                self._rate_limit()

        # Deep GitHub search using the idea + keywords
        logger.info("  ── Deep GitHub Analysis ──")
        github_deep = self.search_github_deep(idea_text, idea_keywords)
        self.global_trends.extend(github_deep)

        # Web search for the idea itself
        if idea_text and len(idea_text) > 10:
            logger.info("  ── Web Search for Idea ──")
            self.global_trends.extend(self.search_web(idea_text[:150]))

        # Deduplicate
        self.global_trends = self._deduplicate(self.global_trends)

        # Remove entries without valid URLs
        self.global_trends = [e for e in self.global_trends if e.get("url")]

        logger.info(f"  Done: {len(self.global_trends)} total unique results (all with valid URLs)")
        logger.info("=" * 60)
        self.save_trends()
        return self.global_trends

    def _deduplicate(self, items):
        seen = set()
        unique = []
        for item in items:
            norm_title = re.sub(r'\s+', ' ', item.get("title", "").lower().strip())
            if norm_title and norm_title not in seen:
                seen.add(norm_title)
                unique.append(item)
        return unique

    # ── Persistence ──────────────────────────────────────────────────────
    def save_trends(self):
        p = os.path.join(DATA_DIR, "global_trends.json")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w', encoding='utf-8') as f:
            json.dump({"scrape_timestamp": datetime.now().isoformat(), "topics": self.topics,
                "total_results": len(self.global_trends),
                "sources_used": ["semantic_scholar", "crossref", "openalex", "github", "web"],
                "entries": self.global_trends}, f, indent=2, default=str)
        logger.info(f"  Saved to: {p}")

    def load_trends(self):
        p = os.path.join(DATA_DIR, "global_trends.json")
        if os.path.exists(p):
            with open(p, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.global_trends = data.get("entries", [])
                return data
        return None

    def get_all_keywords(self):
        kw = set()
        for e in self.global_trends:
            for k in e.get("keywords", []):
                kw.add(k.lower() if isinstance(k, str) else k)
        return sorted(kw)

    def get_keyword_frequencies(self):
        c = Counter()
        for e in self.global_trends:
            for k in e.get("keywords", []):
                c[k.lower() if isinstance(k, str) else k] += 1
        return c.most_common(50)

    def get_combined_documents(self):
        docs = []
        for e in self.global_trends:
            kw = " ".join(k if isinstance(k, str) else str(k) for k in e.get("keywords", []))
            docs.append(f"{e.get('title', '')} {e.get('snippet', '')} {kw}")
        return docs
