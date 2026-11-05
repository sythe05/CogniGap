# CogniGap: An AI-Powered Project Novelty and Overlap Detection Engine

**CogniGap** (formerly Project Indolance) bridges the informal jargon gap for student and developer proposals by translating casual project descriptions into formal academic and technical ontologies, querying multi-domain repositories (ArXiv, Google Patents / PQAI, GitHub, Semantic Scholar, CrossRef, OpenAlex), constructing an integrated **Neo4j Knowledge Graph** and **Qdrant Vector Store**, and executing **GraphRAG multi-hop reasoning** to project an interactive **Blindspot Matrix**.

---

## 🌟 Key Features

1. **LLM Query Expansion Engine**:
   - Translates casual student descriptions into 3–5 formal scientific/technical queries.
   - Extracts architectural technical concepts and potential novelty gaps.
   - Compatible with Google Gemini (recommended), OpenAI GPT-4o, or Groq.

2. **Multi-Domain Data Ingestion**:
   - **Academic Literature**: ArXiv, Semantic Scholar, CrossRef, OpenAlex.
   - **Prior-Art Patents**: PQAI (Patent Quality AI) & Google Patents.
   - **Open-Source Code**: GitHub Search API (repositories, topics, languages, stars, deep search).
   - **Local Knowledge Base**: Scans PDFs, Python, C/C++, Java, Rust, LaTeX, Markdown files.

3. **Knowledge Graph & Vector Storage**:
   - **Neo4j Graph Database**: Models entities (`ProjectIdea`, `Concept`, `ResearchPaper`, `Patent`, `Repository`, `Keyword`, `Document`) and relationships (`[:RELATES_TO]`, `[:HAS_CONCEPT]`, `[:CONTAINS]`, `[:HAS_KEYWORD]`).
   - **Qdrant Vector Database**: Stores high-dimensional dense embeddings for semantic similarity (runs in local embedded mode or client-server mode).

4. **GraphRAG Processing Engine**:
   - Ingests findings into the Knowledge Graph and computes query-scoped overlap from the current search results.
   - Compares project concepts with retrieved papers, patents, and code.
   - Reports a heuristic originality estimate only when relevant matches are found; it is not a calibrated accuracy measure or a legal novelty determination.

5. **Interactive Web Dashboard & Blindspot Matrix**:
   - Next.js (React 18) responsive dark-mode dashboard.
   - Live originality score gauge.
   - Interactive Blindspot Matrix heat grid (Papers vs. Patents vs. Code).
   - Dynamic Knowledge Graph visualization (ArXiv, Patents, GitHub nodes).
   - Search evidence and scoring limitations, with no unvalidated baseline accuracy claims.

6. **Full Backward Compatibility**:
   - Retains all Indolance local scanning, TF-IDF dual-score analysis, plagiarism detection, and the legacy Flask dashboard on port 5000.

---

## 🏗️ System Architecture

```
  Informal Project Idea (Student Proposal)
                   │
                   ▼
       LLM Query Expansion Engine
  (Translates Jargon to Technical Ontology)
                   │
                   ▼
       Multi-Domain Data Sources
   (ArXiv, Patents, GitHub, Semantic Scholar)
                   │
                   ▼
     Knowledge Graph & Vector Storage
       (Neo4j GraphDB & Qdrant Store)
                   │
                   ▼
        GraphRAG Processing Engine
   (Multi-Hop Reasoning & Subgraph Extraction)
                   │
                   ▼
        CogniGap Web Dashboard
           (Next.js / React UI)
                   │
                   ▼
            Blindspot Matrix
   (Interactive Overlap & Gap Visualizer)
```

---

## 💻 Prerequisites & Installation

### Do you need Docker?
- **No, Docker is NOT required** if you have Neo4j Desktop or local Neo4j installed on your laptop!
- Neo4j runs directly on `bolt://localhost:7687`.
- Qdrant runs in **embedded local mode** automatically (in `data/qdrant_store/`), so no separate server or Docker container is required.
- *(Optional)* If you ever prefer Docker, you can run:
  - Neo4j: `docker run -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/yourpassword neo4j:latest`
  - Qdrant: `docker run -p 6333:6333 qdrant/qdrant`

### Required Software:
1. **Python 3.10+**
2. **Node.js 18+ & npm** (for the Next.js frontend)
3. **Neo4j** (installed locally or via Neo4j Desktop)

---

## ⚙️ Quick Start Guide

### 1. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
copy .env.example .env
```
Open `.env` and fill in your credentials:
```env
# Neo4j Settings (Your local Neo4j password)
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_neo4j_password
NEO4J_DATABASE=neo4j

# LLM APIs (Provide one, two, or all — automatic failover waterfall!)
# Whichever works, works! Tries Gemini -> Groq -> OpenAI in sequence:
GEMINI_API_KEY=your_gemini_key
GROQ_API_KEY=your_groq_key
OPENAI_API_KEY=your_openai_key

# Optional: GitHub token for higher rate limits
GITHUB_TOKEN=

# Optional: Semantic Scholar key for higher API rate limits
SEMANTIC_SCHOLAR_API_KEY=
```

Groq requests use the currently recommended `openai/gpt-oss-120b` model. Semantic Scholar
retries a rate-limited request once; if the limit persists, analysis continues with the
other academic sources. Patent search falls back to Google Patents when PQAI is unavailable.

### 2. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 3. Start the FastAPI Backend
```bash
python run_backend.py
# or: python app.py
```
- **Backend API**: `http://localhost:8000`
- **Interactive Swagger Docs**: `http://localhost:8000/docs`
- **Health Check**: `http://localhost:8000/health`

### 4. Start the Next.js Frontend
In a new terminal window:
```bash
cd cognigap-frontend
npm install
npm run dev
```
- Open `http://localhost:3000` in your web browser.

*(Optional)* To view the legacy Flask dashboard on port 5000:
```bash
python app.py --flask
```

---

## 📂 Project Directory Structure

```
indolance/
├── cognigap/                   # CogniGap Core Engine
│   ├── __init__.py
│   ├── config.py               # Central configuration & environment loader
│   ├── query_expansion.py      # LLM-based informal -> technical query translation
│   ├── data_sources.py         # ArXiv & PQAI/Google Patents API connectors
│   ├── neo4j_graph.py          # Neo4j Knowledge Graph schema & multi-hop queries
│   ├── vector_store.py         # Qdrant & sentence-transformers vector engine
│   ├── graphrag_engine.py      # GraphRAG multi-hop reasoning & Blindspot calculations
│   └── api.py                  # FastAPI REST API (/analyze, /health, /stats, /api/*)
│
├── cognigap-frontend/          # Next.js Web Dashboard
│   ├── app/
│   │   ├── globals.css         # Matte-dark futuristic styling & grid animations
│   │   ├── layout.jsx
│   │   └── page.jsx            # Blindspot Matrix, Originality Ring, Graph SVG
│   ├── lib/
│   │   └── api.js              # API bridge connecting to FastAPI backend
│   ├── package.json
│   └── .env.local              # Configured to http://localhost:8000
│
├── chronos/                    # Original Indolance Core Engines
│   ├── local_reader.py         # Document scanning (.pdf, .py, .c, .md)
│   ├── global_scraper.py       # Semantic Scholar, CrossRef, OpenAlex, GitHub
│   ├── comparison_engine.py    # TF-IDF, Cosine Similarity, Plagiarism detection
│   └── utils.py
│
├── data/                       # Local cached results & Qdrant vector store
├── templates/ & static/        # Legacy Flask HTML/CSS/JS dashboard
├── neo4j_db.py                 # Backward-compatible Neo4j script wrapper
├── app.py                      # Unified application launcher (FastAPI or Flask)
├── run_backend.py              # Dedicated FastAPI backend launcher
├── requirements.txt            # Python dependencies
└── .env.example                # Sample environment configuration
```

---
