"""
CogniGap — Configuration
=========================
Central configuration for all modules: LLM, Neo4j, Qdrant, APIs, and analysis.
Merges all Indolance settings with new CogniGap capabilities.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── Base Paths ──────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
STATIC_IMG_DIR = os.path.join(BASE_DIR, "static", "img")
SAMPLE_DIR = os.path.join(BASE_DIR, "sample_files")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(STATIC_IMG_DIR, exist_ok=True)

# ─── Neo4j Settings ─────────────────────────────────────────────────────────
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

# ─── LLM Settings ───────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

def get_available_llm_providers():
    """
    Return all configured LLM providers in priority order.
    Whichever keys are provided will be tried in sequence (automatic failover).
    """
    providers = []
    # 1. Gemini (free, fast, recommended)
    if GEMINI_API_KEY and GEMINI_API_KEY.strip() and not GEMINI_API_KEY.startswith("your_"):
        providers.append(("gemini", GEMINI_API_KEY.strip()))
    # 2. Groq (ultra-fast Llama-3.3, free tier available)
    if GROQ_API_KEY and GROQ_API_KEY.strip() and not GROQ_API_KEY.startswith("your_"):
        providers.append(("groq", GROQ_API_KEY.strip()))
    # 3. OpenAI (GPT-4o mini)
    if OPENAI_API_KEY and OPENAI_API_KEY.strip() and not OPENAI_API_KEY.startswith("your_"):
        providers.append(("openai", OPENAI_API_KEY.strip()))
    return providers

def get_llm_provider():
    """Return (provider, key) for the first configured LLM (backward compatibility)."""
    providers = get_available_llm_providers()
    return providers[0] if providers else (None, None)

# ─── Qdrant Settings ────────────────────────────────────────────────────────
QDRANT_MODE = os.getenv("QDRANT_MODE", "local")          # "local" or "server"
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
QDRANT_COLLECTION = "cognigap_embeddings"
QDRANT_LOCAL_PATH = os.path.join(DATA_DIR, "qdrant_store")

# ─── Part A: Local Reader Settings ──────────────────────────────────────────
SCAN_DIRECTORIES = [
    SAMPLE_DIR,
]

SUPPORTED_EXTENSIONS = {
    ".pdf", ".py", ".c", ".cpp", ".h", ".tex", ".md", ".txt",
    ".java", ".js", ".rs",
}

DOMAIN_KEYWORD_PATTERNS = [
    # Security Hardware & Chips
    r"ATECC608[AB]?", r"TPM\s*2\.0", r"HSM",
    # Networking & Protocols
    r"PCAP", r"IEEE\s*802\.\d+\w*", r"TCP/IP", r"MQTT", r"CoAP",
    r"Zigbee", r"LoRa(?:WAN)?", r"Bluetooth\s*(?:LE|Low\s*Energy)?", r"Wi-?Fi",
    # AI & Machine Learning
    r"(?:deep|machine)\s*learning", r"neural\s*network",
    r"CNN|RNN|LSTM|GAN|transformer", r"TensorFlow|PyTorch|Keras",
    r"reinforcement\s*learning", r"natural\s*language\s*processing|NLP",
    r"computer\s*vision", r"knowledge\s*graph", r"graph\s*rag",
    r"retrieval[\s-]*augmented\s*generation|RAG",
    r"large\s*language\s*model|LLM", r"embedding",
    r"vector\s*database", r"semantic\s*search",
    # IoT & Embedded
    r"IoT", r"Raspberry\s*Pi", r"Arduino", r"ESP32|ESP8266", r"FPGA", r"RTOS",
    r"embedded\s*system",
    # Security Concepts
    r"encryption|AES|RSA|ECC", r"firewall", r"intrusion\s*detection",
    r"penetration\s*testing", r"zero[\s-]*trust", r"blockchain",
    # Cloud & DevOps
    r"Docker|Kubernetes|K8s", r"AWS|Azure|GCP", r"microservice",
    r"CI/CD", r"serverless",
    # Data & Analytics
    r"big\s*data", r"data\s*pipeline", r"ETL", r"data\s*lake",
    # Emerging Tech
    r"quantum\s*computing", r"edge\s*computing", r"digital\s*twin",
    r"5G|6G", r"AR|VR|XR", r"autonomous\s*vehicle",
]

# ─── Part B: API-Based Search Settings ──────────────────────────────────────
# Semantic Scholar
SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper/search"
SEMANTIC_SCHOLAR_FIELDS = "title,abstract,url,year,citationCount,externalIds"
SEMANTIC_SCHOLAR_LIMIT = 15

# CrossRef
CROSSREF_API = "https://api.crossref.org/works"
CROSSREF_LIMIT = 10

# GitHub Search
GITHUB_SEARCH_API = "https://api.github.com/search/repositories"
GITHUB_LIMIT = 15
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

# OpenAlex
OPENALEX_API = "https://api.openalex.org/works"
OPENALEX_LIMIT = 15

# ArXiv (new for CogniGap)
ARXIV_API = "http://export.arxiv.org/api/query"
ARXIV_LIMIT = 15

# PQAI — Patent search (new for CogniGap)
PQAI_API = "https://api.pqai.org/search/102"
PQAI_LIMIT = 10

# Rate limiting
API_DELAY_MIN = 0.5
API_DELAY_MAX = 1.5

API_USER_AGENT = "CogniGap/1.0 (AI-Powered Novelty Detection; Capstone 2026-27)"

# ─── Part C: Comparison Engine Settings ─────────────────────────────────────
LOCAL_SIMILARITY_HIGH = 0.6
LOCAL_SIMILARITY_MEDIUM = 0.25
GLOBAL_SIMILARITY_HIGH = 0.5
GLOBAL_SIMILARITY_MEDIUM = 0.2
PLAGIARISM_SOURCE_THRESHOLD = 0.15
TOP_GAP_SUGGESTIONS = 10

# ─── FastAPI Settings ────────────────────────────────────────────────────────
FASTAPI_HOST = os.getenv("FASTAPI_HOST", "0.0.0.0")
FASTAPI_PORT = int(os.getenv("FASTAPI_PORT", 8000))

# ─── Legacy Flask Settings (kept for fallback dashboard) ─────────────────────
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5000
FLASK_DEBUG = True
