"""
Neo4j Database Connector (Backward-Compatible Wrapper)
======================================================
This module re-exports the full CogniGap Knowledge Graph operations
from `cognigap.neo4j_graph` for backward compatibility with existing scripts.
"""

from cognigap.neo4j_graph import (
    URI, USERNAME, PASSWORD, DATABASE,
    get_driver, test_connection, create_constraints, create_indexes,
    save_document, save_keyword, link_document_keyword,
    save_research_paper, save_repository, save_patent,
    link_paper_keyword, link_repository_keyword, link_patent_keyword,
    save_concept, link_paper_concept, link_patent_concept, link_repo_concept,
    save_project_idea, link_idea_concept,
    get_concept_overlap_subgraph, get_overlapping_works,
    get_knowledge_graph_stats, initialize_graph
)

if __name__ == "__main__":
    try:
        if test_connection():
            print("SUCCESS: CogniGap is connected to Neo4j!")
            initialize_graph()
            stats = get_knowledge_graph_stats()
            print("Graph statistics:", stats)
    except Exception as error:
        print("CONNECTION FAILED:", error)
