"""
CogniGap — Vector Store (Qdrant)
==================================
Manages vector embeddings for semantic similarity search.
Supports local (in-memory/file) and remote Qdrant modes.
Uses sentence-transformers for embedding generation.
"""

import os
import hashlib
import json
import numpy as np
from chronos.utils import logger
from cognigap.config import (
    QDRANT_MODE, QDRANT_URL, QDRANT_API_KEY,
    QDRANT_COLLECTION, QDRANT_LOCAL_PATH, DATA_DIR,
)

# ═══════════════════════════════════════════════════════════
# Embedding Model
# ═══════════════════════════════════════════════════════════

_embedder = None


def _get_embedder():
    """Get or create the sentence-transformers embedder."""
    global _embedder
    if _embedder is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embedder = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("  Loaded embedding model: all-MiniLM-L6-v2")
        except ImportError:
            logger.warning("  sentence-transformers not installed. Using TF-IDF fallback.")
            _embedder = "tfidf"
    return _embedder


def embed_texts(texts):
    """
    Generate embeddings for a list of texts.
    Falls back to TF-IDF if sentence-transformers unavailable.
    """
    embedder = _get_embedder()
    if embedder == "tfidf":
        return _tfidf_embed(texts)
    return embedder.encode(texts, show_progress_bar=False).tolist()


def _tfidf_embed(texts):
    """Fallback TF-IDF embeddings."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    vectorizer = TfidfVectorizer(max_features=384, stop_words="english")
    matrix = vectorizer.fit_transform(texts)
    return matrix.toarray().tolist()


# ═══════════════════════════════════════════════════════════
# Qdrant Client
# ═══════════════════════════════════════════════════════════

_qdrant_client = None


def _get_qdrant_client():
    """Get or create a Qdrant client."""
    global _qdrant_client
    if _qdrant_client is not None:
        return _qdrant_client

    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams

        if QDRANT_MODE == "local":
            os.makedirs(QDRANT_LOCAL_PATH, exist_ok=True)
            _qdrant_client = QdrantClient(path=QDRANT_LOCAL_PATH)
            logger.info(f"  Qdrant local mode at: {QDRANT_LOCAL_PATH}")
        else:
            _qdrant_client = QdrantClient(
                url=QDRANT_URL,
                api_key=QDRANT_API_KEY if QDRANT_API_KEY else None,
            )
            logger.info(f"  Qdrant server mode at: {QDRANT_URL}")

        # Ensure collection exists
        collections = [c.name for c in _qdrant_client.get_collections().collections]
        if QDRANT_COLLECTION not in collections:
            _qdrant_client.create_collection(
                collection_name=QDRANT_COLLECTION,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )
            logger.info(f"  Created Qdrant collection: {QDRANT_COLLECTION}")

        return _qdrant_client

    except ImportError:
        logger.warning("  qdrant-client not installed. Using local JSON vector store.")
        _qdrant_client = "json_fallback"
        return _qdrant_client
    except Exception as e:
        logger.warning(f"  Qdrant initialization failed: {e}. Using JSON fallback.")
        _qdrant_client = "json_fallback"
        return _qdrant_client


# ═══════════════════════════════════════════════════════════
# JSON Fallback Vector Store
# ═══════════════════════════════════════════════════════════

_json_store_path = os.path.join(DATA_DIR, "vector_store.json")


def _load_json_store():
    """Load the JSON-based vector store."""
    if os.path.exists(_json_store_path):
        with open(_json_store_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"vectors": [], "payloads": []}


def _save_json_store(store):
    """Save the JSON-based vector store."""
    os.makedirs(os.path.dirname(_json_store_path), exist_ok=True)
    with open(_json_store_path, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2, default=str)


# ═══════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════

def upsert_documents(documents):
    """
    Embed and store documents in the vector store.

    Args:
        documents: list of dict with keys: id, text, metadata
    """
    if not documents:
        return

    client = _get_qdrant_client()
    texts = [d["text"] for d in documents]
    embeddings = embed_texts(texts)

    if client == "json_fallback":
        store = _load_json_store()
        for doc, emb in zip(documents, embeddings):
            doc_id = doc.get("id", hashlib.md5(doc["text"].encode()).hexdigest())
            store["vectors"].append({"id": doc_id, "vector": emb})
            store["payloads"].append({"id": doc_id, "metadata": doc.get("metadata", {})})
        _save_json_store(store)
        logger.info(f"  Stored {len(documents)} documents in JSON vector store")
    else:
        from qdrant_client.models import PointStruct
        points = []
        for i, (doc, emb) in enumerate(zip(documents, embeddings)):
            doc_id = doc.get("id", hashlib.md5(doc["text"].encode()).hexdigest())
            # Use numeric IDs for Qdrant
            numeric_id = abs(hash(doc_id)) % (2**63)
            points.append(PointStruct(
                id=numeric_id,
                vector=emb,
                payload={"doc_id": doc_id, **doc.get("metadata", {})},
            ))
        client.upsert(collection_name=QDRANT_COLLECTION, points=points)
        logger.info(f"  Stored {len(documents)} documents in Qdrant")


def search_similar(query_text, top_k=10):
    """
    Search for documents similar to the query text.

    Returns:
        list of dict with keys: id, score, metadata
    """
    client = _get_qdrant_client()
    query_embedding = embed_texts([query_text])[0]

    if client == "json_fallback":
        store = _load_json_store()
        if not store["vectors"]:
            return []

        # Cosine similarity search
        results = []
        query_vec = np.array(query_embedding)
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return []

        for vec_entry, payload in zip(store["vectors"], store["payloads"]):
            doc_vec = np.array(vec_entry["vector"])
            doc_norm = np.linalg.norm(doc_vec)
            if doc_norm == 0:
                continue
            score = float(np.dot(query_vec, doc_vec) / (query_norm * doc_norm))
            results.append({
                "id": vec_entry["id"],
                "score": score,
                "metadata": payload.get("metadata", {}),
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]
    else:
        hits = client.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=query_embedding,
            limit=top_k,
        )
        return [
            {"id": hit.payload.get("doc_id", str(hit.id)),
             "score": hit.score,
             "metadata": {k: v for k, v in hit.payload.items() if k != "doc_id"}}
            for hit in hits
        ]


def get_collection_count():
    """Get the number of vectors in the collection."""
    client = _get_qdrant_client()
    if client == "json_fallback":
        store = _load_json_store()
        return len(store["vectors"])
    else:
        info = client.get_collection(QDRANT_COLLECTION)
        return info.points_count


if __name__ == "__main__":
    # Test vector store
    test_docs = [
        {"id": "test1", "text": "Graph neural networks for knowledge representation",
         "metadata": {"source": "test"}},
        {"id": "test2", "text": "Natural language processing with transformers",
         "metadata": {"source": "test"}},
    ]
    upsert_documents(test_docs)
    results = search_similar("knowledge graphs and NLP", top_k=2)
    print("Search results:", json.dumps(results, indent=2))
