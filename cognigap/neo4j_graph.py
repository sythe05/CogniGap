"""
CogniGap — Neo4j Knowledge Graph
==================================
Enhanced knowledge graph for storing and querying papers, patents,
repositories, concepts, and their relationships.
Supports multi-hop reasoning for GraphRAG subgraph extraction.
"""

import os
from neo4j import GraphDatabase
from cognigap.config import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE
from chronos.utils import logger

URI = NEO4J_URI
USERNAME = NEO4J_USERNAME
PASSWORD = NEO4J_PASSWORD
DATABASE = NEO4J_DATABASE


_driver = None


def get_driver():
    """Get or create a Neo4j driver singleton."""
    global _driver
    if _driver is None:
        if not NEO4J_URI or not NEO4J_USERNAME or not NEO4J_PASSWORD:
            raise ValueError(
                "Neo4j not configured. Set NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD in .env"
            )
        _driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
    return _driver


def close_driver():
    """Close the Neo4j driver."""
    global _driver
    if _driver:
        _driver.close()
        _driver = None


def test_connection():
    """Test Neo4j connectivity."""
    try:
        driver = get_driver()
        driver.verify_connectivity()
        with driver.session(database=NEO4J_DATABASE) as session:
            result = session.run("RETURN 1 AS result")
            return result.single()["result"] == 1
    except Exception as e:
        logger.error(f"Neo4j connection failed: {e}")
        return False


# ═══════════════════════════════════════════════════════════
# Schema & Constraints
# ═══════════════════════════════════════════════════════════

def create_constraints():
    """Create uniqueness constraints for all node types."""
    queries = [
        "CREATE CONSTRAINT document_id IF NOT EXISTS "
        "FOR (n:Document) REQUIRE n.id IS UNIQUE",

        "CREATE CONSTRAINT keyword_name IF NOT EXISTS "
        "FOR (n:Keyword) REQUIRE n.name IS UNIQUE",

        "CREATE CONSTRAINT paper_id IF NOT EXISTS "
        "FOR (n:ResearchPaper) REQUIRE n.id IS UNIQUE",

        "CREATE CONSTRAINT repository_id IF NOT EXISTS "
        "FOR (n:Repository) REQUIRE n.id IS UNIQUE",

        "CREATE CONSTRAINT patent_id IF NOT EXISTS "
        "FOR (n:Patent) REQUIRE n.id IS UNIQUE",

        "CREATE CONSTRAINT concept_name IF NOT EXISTS "
        "FOR (n:Concept) REQUIRE n.name IS UNIQUE",

        "CREATE CONSTRAINT project_id IF NOT EXISTS "
        "FOR (n:ProjectIdea) REQUIRE n.id IS UNIQUE",
    ]

    driver = get_driver()
    with driver.session(database=NEO4J_DATABASE) as session:
        for query in queries:
            try:
                session.run(query).consume()
            except Exception as e:
                logger.debug(f"Constraint may already exist: {e}")


def create_indexes():
    """Create full-text indexes for semantic search."""
    queries = [
        "CREATE FULLTEXT INDEX paper_search IF NOT EXISTS "
        "FOR (n:ResearchPaper) ON EACH [n.title, n.snippet]",

        "CREATE FULLTEXT INDEX patent_search IF NOT EXISTS "
        "FOR (n:Patent) ON EACH [n.title, n.snippet]",

        "CREATE FULLTEXT INDEX repo_search IF NOT EXISTS "
        "FOR (n:Repository) ON EACH [n.title, n.snippet]",
    ]

    driver = get_driver()
    with driver.session(database=NEO4J_DATABASE) as session:
        for query in queries:
            try:
                session.run(query).consume()
            except Exception as e:
                logger.debug(f"Index may already exist: {e}")


# ═══════════════════════════════════════════════════════════
# Node Operations
# ═══════════════════════════════════════════════════════════

def save_document(document_id, filename, path, content_hash):
    """Create or update a local document node."""
    query = """
    MERGE (d:Document {id: $document_id})
    SET d.filename = $filename,
        d.path = $path,
        d.content_hash = $content_hash
    RETURN d.id AS id
    """
    driver = get_driver()
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run(query, document_id=document_id,
                             filename=filename, path=path,
                             content_hash=content_hash)
        return result.single()["id"]


def save_keyword(keyword):
    """Create a keyword node."""
    query = """
    MERGE (k:Keyword {name: $keyword})
    RETURN k.name AS name
    """
    driver = get_driver()
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run(query, keyword=keyword.strip().lower())
        return result.single()["name"]


def save_concept(name, description=""):
    """Create or update a concept node (for GraphRAG reasoning)."""
    query = """
    MERGE (c:Concept {name: $name})
    SET c.description = $description
    RETURN c.name AS name
    """
    driver = get_driver()
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run(query, name=name.strip().lower(),
                             description=description)
        return result.single()["name"]


def save_research_paper(paper):
    """Save an academic paper to Neo4j."""
    query = """
    MERGE (p:ResearchPaper {id: $id})
    SET p.title = $title,
        p.snippet = $snippet,
        p.url = $url,
        p.year = $year,
        p.citations = $citations,
        p.source = $source,
        p.source_label = $source_label,
        p.query = $query_text,
        p.scraped_at = $scraped_at
    RETURN p.id AS id
    """
    paper_id = paper.get("url") or (
        str(paper.get("source", "paper")) + ":" +
        str(paper.get("title", "untitled"))
    )
    driver = get_driver()
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run(
            query, id=paper_id,
            title=paper.get("title", ""),
            snippet=paper.get("snippet", ""),
            url=paper.get("url", ""),
            year=paper.get("year"),
            citations=paper.get("citations", 0),
            source=paper.get("source", ""),
            source_label=paper.get("source_label", ""),
            query_text=paper.get("query", ""),
            scraped_at=paper.get("scraped_at", ""),
        )
        return result.single()["id"]


def save_patent(patent):
    """Save a patent to Neo4j."""
    query = """
    MERGE (p:Patent {id: $id})
    SET p.title = $title,
        p.snippet = $snippet,
        p.url = $url,
        p.year = $year,
        p.source = $source,
        p.source_label = $source_label,
        p.query = $query_text,
        p.scraped_at = $scraped_at
    RETURN p.id AS id
    """
    patent_id = patent.get("url") or patent.get("title", "unknown-patent")
    driver = get_driver()
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run(
            query, id=patent_id,
            title=patent.get("title", ""),
            snippet=patent.get("snippet", ""),
            url=patent.get("url", ""),
            year=patent.get("year"),
            source=patent.get("source", "patent"),
            source_label=patent.get("source_label", "Patent"),
            query_text=patent.get("query", ""),
            scraped_at=patent.get("scraped_at", ""),
        )
        return result.single()["id"]


def save_repository(repo):
    """Save a GitHub repository to Neo4j."""
    query = """
    MERGE (r:Repository {id: $id})
    SET r.title = $title,
        r.snippet = $snippet,
        r.url = $url,
        r.year = $year,
        r.stars = $stars,
        r.forks = $forks,
        r.language = $language,
        r.topics = $topics,
        r.source = $source,
        r.source_label = $source_label,
        r.query = $query_text,
        r.scraped_at = $scraped_at
    RETURN r.id AS id
    """
    repo_id = repo.get("url") or repo.get("title", "unknown-repository")
    driver = get_driver()
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run(
            query, id=repo_id,
            title=repo.get("title", ""),
            snippet=repo.get("snippet", ""),
            url=repo.get("url", ""),
            year=repo.get("year"),
            stars=repo.get("stars", 0),
            forks=repo.get("forks", 0),
            language=repo.get("language", ""),
            topics=repo.get("topics", []),
            source=repo.get("source", "github"),
            source_label=repo.get("source_label", "GitHub Repository"),
            query_text=repo.get("query", ""),
            scraped_at=repo.get("scraped_at", ""),
        )
        return result.single()["id"]


def save_project_idea(idea_id, description, expanded_queries=None):
    """Save the user's project idea as a node."""
    query = """
    MERGE (p:ProjectIdea {id: $id})
    SET p.description = $description,
        p.expanded_queries = $queries
    RETURN p.id AS id
    """
    driver = get_driver()
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run(
            query, id=idea_id, description=description,
            queries=expanded_queries or [],
        )
        return result.single()["id"]


# ═══════════════════════════════════════════════════════════
# Relationship Operations
# ═══════════════════════════════════════════════════════════

def link_document_keyword(document_id, keyword):
    """Connect a document to a keyword."""
    query = """
    MATCH (d:Document {id: $document_id})
    MATCH (k:Keyword {name: $keyword})
    MERGE (d)-[:CONTAINS]->(k)
    RETURN d.id AS document_id
    """
    driver = get_driver()
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run(query, document_id=document_id,
                             keyword=keyword.strip().lower())
        return result.single() is not None


def link_paper_keyword(paper_id, keyword):
    """Connect a research paper to a keyword."""
    save_keyword(keyword)
    query = """
    MATCH (p:ResearchPaper {id: $paper_id})
    MATCH (k:Keyword {name: $keyword})
    MERGE (p)-[:HAS_KEYWORD]->(k)
    RETURN p.id AS paper_id
    """
    driver = get_driver()
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run(query, paper_id=paper_id,
                             keyword=keyword.strip().lower())
        return result.single() is not None


def link_repository_keyword(repo_id, keyword):
    """Connect a GitHub repository to a keyword."""
    save_keyword(keyword)
    query = """
    MATCH (r:Repository {id: $repo_id})
    MATCH (k:Keyword {name: $keyword})
    MERGE (r)-[:HAS_KEYWORD]->(k)
    RETURN r.id AS repo_id
    """
    driver = get_driver()
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run(query, repo_id=repo_id,
                             keyword=keyword.strip().lower())
        return result.single() is not None


def link_patent_keyword(patent_id, keyword):
    """Connect a patent to a keyword."""
    save_keyword(keyword)
    query = """
    MATCH (p:Patent {id: $patent_id})
    MATCH (k:Keyword {name: $keyword})
    MERGE (p)-[:HAS_KEYWORD]->(k)
    RETURN p.id AS patent_id
    """
    driver = get_driver()
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run(query, patent_id=patent_id,
                             keyword=keyword.strip().lower())
        return result.single() is not None


def link_paper_concept(paper_id, concept_name, similarity=0.0):
    """Connect a paper to a concept with overlap score."""
    save_concept(concept_name)
    query = """
    MATCH (p:ResearchPaper {id: $paper_id})
    MATCH (c:Concept {name: $concept_name})
    MERGE (p)-[r:RELATES_TO]->(c)
    SET r.similarity = $similarity
    RETURN p.id AS paper_id
    """
    driver = get_driver()
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run(query, paper_id=paper_id,
                             concept_name=concept_name.strip().lower(),
                             similarity=similarity)
        return result.single() is not None


def link_patent_concept(patent_id, concept_name, similarity=0.0):
    """Connect a patent to a concept."""
    save_concept(concept_name)
    query = """
    MATCH (p:Patent {id: $patent_id})
    MATCH (c:Concept {name: $concept_name})
    MERGE (p)-[r:RELATES_TO]->(c)
    SET r.similarity = $similarity
    RETURN p.id AS patent_id
    """
    driver = get_driver()
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run(query, patent_id=patent_id,
                             concept_name=concept_name.strip().lower(),
                             similarity=similarity)
        return result.single() is not None


def link_repo_concept(repo_id, concept_name, similarity=0.0):
    """Connect a repository to a concept."""
    save_concept(concept_name)
    query = """
    MATCH (r:Repository {id: $repo_id})
    MATCH (c:Concept {name: $concept_name})
    MERGE (r)-[rel:RELATES_TO]->(c)
    SET rel.similarity = $similarity
    RETURN r.id AS repo_id
    """
    driver = get_driver()
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run(query, repo_id=repo_id,
                             concept_name=concept_name.strip().lower(),
                             similarity=similarity)
        return result.single() is not None


def link_idea_concept(idea_id, concept_name):
    """Connect a project idea to a concept."""
    save_concept(concept_name)
    query = """
    MATCH (p:ProjectIdea {id: $idea_id})
    MATCH (c:Concept {name: $concept_name})
    MERGE (p)-[:HAS_CONCEPT]->(c)
    RETURN p.id AS idea_id
    """
    driver = get_driver()
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run(query, idea_id=idea_id,
                             concept_name=concept_name.strip().lower())
        return result.single() is not None


# ═══════════════════════════════════════════════════════════
# GraphRAG — Multi-hop Reasoning Queries
# ═══════════════════════════════════════════════════════════

def get_concept_overlap_subgraph(concept_names):
    """
    Multi-hop query: given a list of concept names, find all papers,
    patents, and repos connected to those concepts, and compute
    overlap scores per concept per source type.

    Returns:
        dict: { concept_name: { papers: float, patents: float, code: float } }
    """
    query = """
    UNWIND $concepts AS concept_name
    MATCH (c:Concept {name: concept_name})
    OPTIONAL MATCH (p:ResearchPaper)-[r1:RELATES_TO]->(c)
    OPTIONAL MATCH (pat:Patent)-[r2:RELATES_TO]->(c)
    OPTIONAL MATCH (repo:Repository)-[r3:RELATES_TO]->(c)
    RETURN concept_name,
           avg(r1.similarity) AS paper_overlap,
           count(DISTINCT p) AS paper_count,
           avg(r2.similarity) AS patent_overlap,
           count(DISTINCT pat) AS patent_count,
           avg(r3.similarity) AS code_overlap,
           count(DISTINCT repo) AS repo_count
    """
    driver = get_driver()
    result_map = {}
    with driver.session(database=NEO4J_DATABASE) as session:
        results = session.run(query, concepts=[c.strip().lower() for c in concept_names])
        for record in results:
            name = record["concept_name"]
            result_map[name] = {
                "papers": round(float(record["paper_overlap"] or 0), 2),
                "paper_count": record["paper_count"],
                "patents": round(float(record["patent_overlap"] or 0), 2),
                "patent_count": record["patent_count"],
                "code": round(float(record["code_overlap"] or 0), 2),
                "repo_count": record["repo_count"],
            }
    return result_map


def get_overlapping_works(concept_names, min_similarity=0.1, limit=30):
    """
    Multi-hop: find all works related to the given concepts that have
    meaningful similarity, with the concept connections listed.

    Returns list of { title, source, url, similarity, concepts }
    """
    query = """
    UNWIND $concepts AS concept_name
    MATCH (c:Concept {name: concept_name})
    MATCH (work)-[r:RELATES_TO]->(c)
    WHERE r.similarity >= $min_sim
    WITH work, c.name AS concept_name, r.similarity AS sim,
         labels(work) AS labels
    WITH work,
         collect(concept_name) AS concepts,
         max(sim) AS max_sim,
         CASE
           WHEN 'ResearchPaper' IN labels(work) THEN 'arxiv'
           WHEN 'Patent' IN labels(work) THEN 'patent'
           WHEN 'Repository' IN labels(work) THEN 'github'
           ELSE 'unknown'
         END AS source
    RETURN work.title AS title,
           source,
           work.url AS url,
           max_sim AS similarity,
           concepts
    ORDER BY similarity DESC
    LIMIT $limit
    """
    driver = get_driver()
    overlaps = []
    with driver.session(database=NEO4J_DATABASE) as session:
        results = session.run(
            query,
            concepts=[c.strip().lower() for c in concept_names],
            min_sim=min_similarity,
            limit=limit,
        )
        for record in results:
            overlaps.append({
                "title": record["title"] or "Untitled",
                "source": record["source"],
                "url": record["url"] or "#",
                "similarity": round(float(record["similarity"]), 2),
                "concepts": record["concepts"],
            })
    return overlaps


def get_knowledge_graph_stats():
    """Get counts of all node and relationship types."""
    query = """
    CALL {
        MATCH (p:ResearchPaper) RETURN 'papers' AS label, count(p) AS cnt
        UNION ALL
        MATCH (pat:Patent) RETURN 'patents' AS label, count(pat) AS cnt
        UNION ALL
        MATCH (r:Repository) RETURN 'repos' AS label, count(r) AS cnt
        UNION ALL
        MATCH (c:Concept) RETURN 'concepts' AS label, count(c) AS cnt
        UNION ALL
        MATCH (k:Keyword) RETURN 'keywords' AS label, count(k) AS cnt
        UNION ALL
        MATCH ()-[r:RELATES_TO]->() RETURN 'relationships' AS label, count(r) AS cnt
    }
    RETURN label, cnt
    """
    driver = get_driver()
    stats = {}
    with driver.session(database=NEO4J_DATABASE) as session:
        try:
            results = session.run(query)
            for record in results:
                stats[record["label"]] = record["cnt"]
        except Exception as e:
            logger.error(f"Failed to get graph stats: {e}")
    return stats


def clear_graph():
    """Clear all data from the knowledge graph. Use with caution."""
    driver = get_driver()
    with driver.session(database=NEO4J_DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n").consume()
    logger.info("Knowledge graph cleared")


# ═══════════════════════════════════════════════════════════
# Initialization
# ═══════════════════════════════════════════════════════════

def initialize_graph():
    """Set up constraints and indexes. Call on startup."""
    try:
        if test_connection():
            create_constraints()
            create_indexes()
            logger.info("Neo4j knowledge graph initialized successfully")
            return True
    except Exception as e:
        logger.warning(f"Neo4j initialization failed (non-fatal): {e}")
    return False


if __name__ == "__main__":
    try:
        if test_connection():
            print("SUCCESS: CogniGap is connected to Neo4j!")
            initialize_graph()
            stats = get_knowledge_graph_stats()
            print(f"Graph stats: {stats}")
    except Exception as error:
        print("CONNECTION FAILED:", error)
