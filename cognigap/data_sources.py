"""
CogniGap — ArXiv & Patent Search
===================================
Additional data source integrations for CogniGap:
- ArXiv API (academic papers)
- PQAI API (patent prior-art search)
"""

import re
import time
import random
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import quote_plus

import requests
from chronos.utils import logger, extract_words
from cognigap.config import (
    ARXIV_API, ARXIV_LIMIT,
    PQAI_API, PQAI_LIMIT,
    API_DELAY_MIN, API_DELAY_MAX, API_USER_AGENT,
)


class ArxivSearcher:
    """Search ArXiv for academic papers using the ArXiv API."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": API_USER_AGENT})

    def search(self, query, limit=None):
        """
        Search ArXiv for papers matching the query.

        Returns:
            list of dict: Each with title, snippet, url, year, source, etc.
        """
        limit = limit or ARXIV_LIMIT
        results = []
        logger.info(f"  [ArXiv] Searching: '{query}'")

        try:
            params = {
                "search_query": f"all:{quote_plus(query)}",
                "start": 0,
                "max_results": limit,
                "sortBy": "relevance",
                "sortOrder": "descending",
            }
            resp = self.session.get(ARXIV_API, params=params, timeout=20)
            resp.raise_for_status()

            # Parse XML response
            root = ET.fromstring(resp.text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}

            for entry in root.findall("atom:entry", ns):
                title_el = entry.find("atom:title", ns)
                summary_el = entry.find("atom:summary", ns)
                published_el = entry.find("atom:published", ns)
                id_el = entry.find("atom:id", ns)

                if title_el is None:
                    continue

                title = re.sub(r"\s+", " ", title_el.text or "").strip()
                summary = re.sub(r"\s+", " ", (summary_el.text or "")).strip()
                arxiv_url = (id_el.text or "").strip()
                published = (published_el.text or "")[:10]
                year = int(published[:4]) if published else None

                # Get PDF link
                pdf_link = ""
                for link in entry.findall("atom:link", ns):
                    if link.get("title") == "pdf":
                        pdf_link = link.get("href", "")

                # Get authors
                authors = []
                for author in entry.findall("atom:author", ns):
                    name_el = author.find("atom:name", ns)
                    if name_el is not None:
                        authors.append(name_el.text)

                # Get categories
                categories = []
                for cat in entry.findall("atom:category", ns):
                    term = cat.get("term", "")
                    if term:
                        categories.append(term)

                results.append({
                    "title": title,
                    "snippet": summary[:500],
                    "url": arxiv_url,
                    "pdf_url": pdf_link,
                    "year": year,
                    "citations": 0,  # ArXiv doesn't provide citation counts
                    "authors": authors[:5],
                    "categories": categories,
                    "source": "arxiv",
                    "source_label": "ArXiv Paper",
                    "query": query,
                    "keywords": extract_words(f"{title} {summary}")[:15],
                    "scraped_at": datetime.now().isoformat(),
                })

            logger.info(f"    Found {len(results)} papers from ArXiv")
        except Exception as ex:
            logger.error(f"    ArXiv search failed: {ex}")

        return results


class PatentSearcher:
    """Search patents using the PQAI (Patent Quality AI) free API."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": API_USER_AGENT,
            "Content-Type": "application/json",
        })

    def search(self, query, limit=None):
        """
        Search patents using PQAI API.

        Returns:
            list of dict: Each with title, snippet, url, year, source, etc.
        """
        limit = limit or PQAI_LIMIT
        results = []
        logger.info(f"  [Patents] Searching: '{query}'")

        try:
            resp = self.session.get(
                PQAI_API,
                params={"q": query, "n": limit, "type": "patent"},
                timeout=20,
            )

            if resp.status_code == 200:
                data = resp.json()
                patents = data if isinstance(data, list) else data.get("results", [])

                for patent in patents[:limit]:
                    title = patent.get("title", "")
                    if not title:
                        continue

                    abstract = patent.get("abstract", "") or ""
                    pub_number = patent.get("publication_number", "") or patent.get("id", "")
                    pub_date = patent.get("publication_date", "") or ""
                    year = int(pub_date[:4]) if pub_date and len(pub_date) >= 4 else None

                    # Build patent URL
                    url = ""
                    if pub_number:
                        url = f"https://patents.google.com/patent/{pub_number}"
                    elif patent.get("url"):
                        url = patent["url"]

                    results.append({
                        "title": title,
                        "snippet": abstract[:500],
                        "url": url,
                        "year": year,
                        "publication_number": pub_number,
                        "source": "patent",
                        "source_label": "Patent",
                        "query": query,
                        "keywords": extract_words(f"{title} {abstract}")[:15],
                        "scraped_at": datetime.now().isoformat(),
                    })

                logger.info(f"    Found {len(results)} patents")
            else:
                logger.warning(f"    PQAI returned status {resp.status_code}")

        except Exception as ex:
            logger.error(f"    Patent search failed: {ex}")

        return results

    def search_google_patents(self, query, limit=None):
        """
        Fallback: search Google Patents via their public API.
        """
        limit = limit or PQAI_LIMIT
        results = []
        logger.info(f"  [Google Patents] Searching: '{query}'")

        try:
            resp = self.session.get(
                "https://patents.google.com/xhr/query",
                params={"url": f"q={quote_plus(query)}&num={limit}"},
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                clusters = data.get("results", {}).get("cluster", [])
                for cluster in clusters:
                    for result in cluster.get("result", []):
                        patent = result.get("patent", {})
                        title = patent.get("title", "")
                        abstract = patent.get("abstract", "")
                        pub_number = patent.get("publication_number", "")
                        if title:
                            url = f"https://patents.google.com/patent/{pub_number}" if pub_number else ""
                            results.append({
                                "title": title,
                                "snippet": abstract[:500],
                                "url": url,
                                "year": None,
                                "source": "patent",
                                "source_label": "Google Patent",
                                "query": query,
                                "keywords": extract_words(f"{title} {abstract}")[:15],
                                "scraped_at": datetime.now().isoformat(),
                            })
                logger.info(f"    Found {len(results)} patents from Google")
        except Exception as ex:
            logger.error(f"    Google Patents search failed: {ex}")

        return results


def rate_limit(extra=0):
    """Rate limit between API calls."""
    time.sleep(random.uniform(API_DELAY_MIN, API_DELAY_MAX) + extra)
