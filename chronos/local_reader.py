"""
Project CogniGap — Part A: The Local Reader (The "Past")
========================================================
Scans local directories for PDFs, code files, and documents.
Extracts keywords using regex patterns and frequency analysis.
Builds a timestamped knowledge base of what you already know.
"""

import os
import re
import json
from collections import Counter
from datetime import datetime

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import (
    SCAN_DIRECTORIES, SUPPORTED_EXTENSIONS,
    DOMAIN_KEYWORD_PATTERNS, DATA_DIR
)
from chronos.utils import (
    logger, clean_text, extract_words, get_file_timestamp,
    get_file_extension, is_binary_file, truncate_text
)


class LocalReader:
    """
    Scans local files, extracts text and keywords, and builds
    a timestamped knowledge base.
    """

    def __init__(self, scan_dirs=None):
        self.scan_dirs = scan_dirs or SCAN_DIRECTORIES
        self.compiled_patterns = [
            re.compile(p, re.IGNORECASE) for p in DOMAIN_KEYWORD_PATTERNS
        ]
        self.knowledge_base = []

    # ─── File Discovery ──────────────────────────────────────────────────

    def discover_files(self):
        """
        Recursively find all supported files in configured directories.

        Returns:
            list of str: Absolute paths to discovered files.
        """
        discovered = []
        for scan_dir in self.scan_dirs:
            if not os.path.isdir(scan_dir):
                logger.warning(f"Scan directory not found: {scan_dir}")
                continue

            for root, dirs, files in os.walk(scan_dir):
                # Skip hidden directories and common non-relevant dirs
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in {
                    'node_modules', '__pycache__', '.git', 'venv', 'env',
                    '.venv', '.env', 'dist', 'build'
                }]

                for filename in files:
                    ext = get_file_extension(filename)
                    if ext in SUPPORTED_EXTENSIONS:
                        filepath = os.path.join(root, filename)
                        discovered.append(filepath)

        logger.info(f"Discovered {len(discovered)} files across {len(self.scan_dirs)} directories")
        return discovered

    # ─── Text Extraction ─────────────────────────────────────────────────

    def extract_text_from_pdf(self, filepath):
        """Extract text from a PDF file using pdfplumber."""
        if not HAS_PDFPLUMBER:
            logger.warning("pdfplumber not installed. Skipping PDF: %s", filepath)
            return ""

        try:
            text = ""
            with pdfplumber.open(filepath) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            return text
        except Exception as e:
            logger.error(f"Failed to extract PDF text from {filepath}: {e}")
            return ""

    def extract_text_from_code(self, filepath):
        """Extract text from a code/text file."""
        if is_binary_file(filepath):
            logger.debug(f"Skipping binary file: {filepath}")
            return ""

        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read file {filepath}: {e}")
            return ""

    def extract_text(self, filepath):
        """Extract text from any supported file type."""
        ext = get_file_extension(filepath)
        if ext == '.pdf':
            return self.extract_text_from_pdf(filepath)
        else:
            return self.extract_text_from_code(filepath)

    # ─── Keyword Extraction ──────────────────────────────────────────────

    def extract_domain_keywords(self, text):
        """
        Extract domain-specific keywords using regex patterns.

        Returns:
            list of dict: Each with {keyword, pattern, count}
        """
        found = []
        for pattern in self.compiled_patterns:
            matches = pattern.findall(text)
            if matches:
                # Normalize the keyword to a canonical form
                canonical = matches[0].strip()
                found.append({
                    "keyword": canonical,
                    "pattern": pattern.pattern,
                    "count": len(matches),
                    "type": "domain"
                })
        return found

    def extract_frequency_keywords(self, text, top_n=20):
        """
        Extract top-N keywords by frequency after stopword removal.

        Returns:
            list of dict: Each with {keyword, count}
        """
        words = extract_words(text)
        counter = Counter(words)
        return [
            {"keyword": word, "count": count, "type": "frequency"}
            for word, count in counter.most_common(top_n)
        ]

    def extract_keywords(self, text):
        """
        Full keyword extraction: domain patterns + frequency analysis.

        Returns:
            list of dict: Combined keyword list.
        """
        domain_kw = self.extract_domain_keywords(text)
        freq_kw = self.extract_frequency_keywords(text)

        # Merge, avoiding duplicates (domain keywords take priority)
        domain_names = {kw["keyword"].lower() for kw in domain_kw}
        combined = domain_kw.copy()
        for kw in freq_kw:
            if kw["keyword"].lower() not in domain_names:
                combined.append(kw)

        return combined

    # ─── Knowledge Base Building ─────────────────────────────────────────

    def process_file(self, filepath):
        """
        Process a single file: extract text, find keywords, timestamp.

        Returns:
            dict: File entry with metadata and keywords.
        """
        logger.debug(f"Processing: {filepath}")

        text = self.extract_text(filepath)
        if not text or len(text.strip()) < 10:
            logger.debug(f"Skipping empty/minimal file: {filepath}")
            return None

        keywords = self.extract_keywords(text)
        if not keywords:
            return None

        # Build a context snippet (first 300 chars of cleaned text)
        snippet = truncate_text(clean_text(text), 300)

        entry = {
            "source_file": filepath,
            "filename": os.path.basename(filepath),
            "extension": get_file_extension(filepath),
            "timestamp": get_file_timestamp(filepath),
            "text_length": len(text),
            "keywords": keywords,
            "snippet": snippet,
            "scanned_at": datetime.now().isoformat()
        }

        return entry

    def scan_all(self):
        """
        Run the full local scan pipeline:
        1. Discover files
        2. Extract text & keywords from each
        3. Build the timestamped knowledge base

        Returns:
            list of dict: The complete knowledge base.
        """
        logger.info("═" * 60)
        logger.info("  COGNIGAP — Part A: Local Reader — Starting Scan")
        logger.info("═" * 60)

        files = self.discover_files()
        self.knowledge_base = []

        for i, filepath in enumerate(files, 1):
            logger.info(f"  [{i}/{len(files)}] Scanning: {os.path.basename(filepath)}")
            entry = self.process_file(filepath)
            if entry:
                self.knowledge_base.append(entry)

        logger.info(f"  Scan complete: {len(self.knowledge_base)} files with keywords")
        logger.info("═" * 60)

        # Save to disk
        self.save_knowledge_base()
        return self.knowledge_base

    # ─── Persistence ─────────────────────────────────────────────────────

    def save_knowledge_base(self):
        """Save the knowledge base to a JSON file."""
        output_path = os.path.join(DATA_DIR, "local_keywords.json")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        data = {
            "scan_timestamp": datetime.now().isoformat(),
            "scan_directories": self.scan_dirs,
            "total_files": len(self.knowledge_base),
            "entries": self.knowledge_base
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)

        logger.info(f"  Knowledge base saved to: {output_path}")
        return output_path

    def load_knowledge_base(self):
        """Load existing knowledge base from disk."""
        input_path = os.path.join(DATA_DIR, "local_keywords.json")
        if os.path.exists(input_path):
            with open(input_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.knowledge_base = data.get("entries", [])
                logger.info(f"  Loaded {len(self.knowledge_base)} entries from cache")
                return data
        return None

    # ─── Aggregation Helpers ─────────────────────────────────────────────

    def get_all_keywords(self):
        """Get a flat list of all unique keywords across all files."""
        all_kw = set()
        for entry in self.knowledge_base:
            for kw in entry.get("keywords", []):
                all_kw.add(kw["keyword"].lower())
        return sorted(all_kw)

    def get_keyword_timeline(self):
        """
        Build a timeline of keywords sorted by file timestamp.

        Returns:
            list of dict: [{timestamp, file, keywords}]
        """
        timeline = []
        for entry in self.knowledge_base:
            timeline.append({
                "timestamp": entry["timestamp"],
                "file": entry["filename"],
                "keywords": [kw["keyword"] for kw in entry["keywords"][:10]]
            })
        timeline.sort(key=lambda x: x["timestamp"])
        return timeline

    def get_combined_text(self):
        """Get all extracted text combined into one string for vectorization."""
        texts = []
        for entry in self.knowledge_base:
            kw_text = " ".join(kw["keyword"] for kw in entry.get("keywords", []))
            texts.append(kw_text)
        return " ".join(texts)
