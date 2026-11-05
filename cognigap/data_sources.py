"""
CogniGap — Academic & Patent Data Sources
===========================================
Integrations for CogniGap:
- Google Patents (via Patents XHR + BeautifulSoup parsing)
- ArXiv API (academic papers)
- Europe PMC API (open academic literature)
- Free, reliable prior-art search across millions of works.
"""

import re
import time
import random
import html
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import quote_plus
import requests
from bs4 import BeautifulSoup

from chronos.utils import logger, extract_words
from cognigap.config import (
    ARXIV_API, ARXIV_LIMIT,
    API_DELAY_MIN, API_DELAY_MAX, API_USER_AGENT,
)


class ArxivSearcher:
    """Search ArXiv for academic papers using the official ArXiv API."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": API_USER_AGENT})

    def search(self, query, limit=None):
        """
        Search ArXiv for papers matching the query.
        """
        limit = limit or ARXIV_LIMIT
        results = []
        logger.info(f"  [ArXiv] Searching: '{query}'")

        try:
            # Note: Do NOT use quote_plus here; requests params handles encoding.
            clean_q = re.sub(r'["\']', '', query).strip()
            params = {
                "search_query": f"all:{clean_q}",
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

                raw_title = title_el.text or ""
                title = re.sub(r"\s+", " ", BeautifulSoup(raw_title, "html.parser").get_text()).strip()
                raw_summary = summary_el.text or "" if summary_el is not None else ""
                summary = re.sub(r"\s+", " ", BeautifulSoup(raw_summary, "html.parser").get_text()).strip()
                arxiv_url = (id_el.text or "").strip() if id_el is not None else ""
                published = (published_el.text or "")[:10] if published_el is not None else ""
                year = int(published[:4]) if published and published[:4].isdigit() else None

                # Get PDF link
                pdf_link = ""
                for link in entry.findall("atom:link", ns):
                    if link.get("title") == "pdf":
                        pdf_link = link.get("href", "")

                # Get authors
                authors = []
                for author in entry.findall("atom:author", ns):
                    name_el = author.find("atom:name", ns)
                    if name_el is not None and name_el.text:
                        authors.append(name_el.text.strip())

                if not title:
                    continue

                results.append({
                    "title": title,
                    "snippet": summary[:500],
                    "url": arxiv_url,
                    "pdf_url": pdf_link,
                    "year": year,
                    "citations": 0,
                    "authors": authors[:5],
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


class EuropePmcSearcher:
    """Search Europe PMC for comprehensive open-access academic literature."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": API_USER_AGENT})

    def search(self, query, limit=12):
        results = []
        logger.info(f"  [Europe PMC] Searching: '{query}'")
        try:
            clean_q = re.sub(r'["\']', '', query).strip()
            url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
            params = {
                "query": clean_q,
                "format": "json",
                "pageSize": limit,
                "resultType": "core",
            }
            resp = self.session.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("resultList", {}).get("result", [])
                for item in items:
                    raw_title = item.get("title", "")
                    title = BeautifulSoup(raw_title, "html.parser").get_text().strip()
                    if not title:
                        continue
                    raw_abstract = item.get("abstractText", "") or ""
                    abstract = BeautifulSoup(raw_abstract, "html.parser").get_text().strip()
                    doi = item.get("doi", "")
                    url_out = f"https://doi.org/{doi}" if doi else ""
                    if not url_out and item.get("pmcid"):
                        url_out = f"https://europepmc.org/article/PMC/{item['pmcid']}"
                    elif not url_out and item.get("id"):
                        url_out = f"https://europepmc.org/article/MED/{item['id']}"

                    year = None
                    pub_year = item.get("pubYear")
                    if pub_year and str(pub_year).isdigit():
                        year = int(pub_year)

                    results.append({
                        "title": title,
                        "snippet": abstract[:500],
                        "url": url_out,
                        "year": year,
                        "citations": item.get("citedByCount", 0),
                        "source": "europe_pmc",
                        "source_label": "Europe PMC Paper",
                        "query": query,
                        "keywords": extract_words(f"{title} {abstract}")[:15],
                        "scraped_at": datetime.now().isoformat(),
                    })
                logger.info(f"    Found {len(results)} papers from Europe PMC")
        except Exception as ex:
            logger.warning(f"    Europe PMC search failed: {ex}")
        return results


class PatentSearcher:
    """Search Google Patents using XHR and BeautifulSoup HTML cleanup."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
        })

    def search(self, query, limit=10):
        """
        Search Google Patents directly.
        Returns:
            list of dict: Each with title, snippet, url, year, publication_number, etc.
        """
        results = []
        logger.info(f"  [Patents] Searching Google Patents: '{query}'")

        try:
            clean_q = re.sub(r'["\']', '', query).strip()
            encoded_query = quote_plus(clean_q)
            resp = self.session.get(
                "https://patents.google.com/xhr/query",
                params={"url": f"q={encoded_query}&num={limit}"},
                timeout=18,
            )

            if resp.status_code == 200:
                data = resp.json()
                clusters = data.get("results", {}).get("cluster", [])
                for cluster in clusters:
                    for result in cluster.get("result", []):
                        patent = result.get("patent", {})
                        raw_title = patent.get("title", "") or ""
                        # Use BeautifulSoup to clean HTML tags & entities
                        title = BeautifulSoup(raw_title, "html.parser").get_text().strip()
                        raw_snippet = patent.get("abstract") or patent.get("snippet", "") or ""
                        snippet = BeautifulSoup(raw_snippet, "html.parser").get_text().strip()
                        pub_number = patent.get("publication_number", "")
                        pub_date = patent.get("publication_date", "") or ""
                        year = int(pub_date[:4]) if pub_date[:4].isdigit() else None

                        if title:
                            url = f"https://patents.google.com/patent/{pub_number}" if pub_number else ""
                            results.append({
                                "title": title,
                                "snippet": snippet[:500],
                                "url": url,
                                "year": year,
                                "publication_number": pub_number,
                                "source": "patent",
                                "source_label": "Patent",
                                "query": query,
                                "keywords": extract_words(f"{title} {snippet}")[:15],
                                "scraped_at": datetime.now().isoformat(),
                            })
                        if len(results) >= limit:
                            break
                    if len(results) >= limit:
                        break

                logger.info(f"    Found {len(results)} patents")
            else:
                logger.warning(f"    Google Patents returned status {resp.status_code}")

        except Exception as ex:
            logger.error(f"    Google Patents search failed: {ex}")

        return results


def rate_limit(extra=0):
    """Rate limit between API calls."""
    time.sleep(random.uniform(API_DELAY_MIN, API_DELAY_MAX) + extra)
