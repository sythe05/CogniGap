import unittest
from unittest.mock import patch

import requests

from chronos import global_scraper
from cognigap import data_sources, query_expansion
from cognigap.graphrag_engine import GraphRAGEngine


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = headers or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class ProviderIntegrationTests(unittest.TestCase):
    @patch("cognigap.query_expansion.requests.post")
    def test_groq_uses_supported_model_and_api_key(self, post):
        post.return_value = FakeResponse(
            payload={"choices": [{"message": {"content": "expanded"}}]}
        )

        result = query_expansion._call_groq("prompt", "test-groq-key")

        self.assertEqual(result, "expanded")
        self.assertEqual(
            post.call_args.kwargs["headers"]["Authorization"],
            "Bearer test-groq-key",
        )
        self.assertEqual(
            post.call_args.kwargs["json"]["model"], "openai/gpt-oss-120b"
        )

    @patch("chronos.global_scraper.time.sleep")
    @patch.object(global_scraper, "SEMANTIC_SCHOLAR_API_KEY", "test-scholar-key")
    def test_semantic_scholar_retries_rate_limit_with_api_key(self, sleep):
        scraper = global_scraper.GlobalScraper()
        scraper.session.get = unittest.mock.Mock(side_effect=[
            FakeResponse(status_code=429, headers={"Retry-After": "1"}),
            FakeResponse(payload={"data": []}),
        ])

        results = scraper.search_semantic_scholar("test query")

        self.assertEqual(results, [])
        self.assertEqual(scraper.session.get.call_count, 2)
        self.assertEqual(
            scraper.session.get.call_args.kwargs["headers"]["x-api-key"],
            "test-scholar-key",
        )
        sleep.assert_called_once_with(1.0)

    def test_patent_search_falls_back_to_google_after_pqai_error(self):
        searcher = data_sources.PatentSearcher()
        google_response = FakeResponse(payload={
            "results": {
                "cluster": [{
                    "result": [{
                        "patent": {
                            "title": "A <b>sample</b> patent",
                            "snippet": "An &hellip; description",
                            "publication_number": "US1234567A1",
                            "publication_date": "20240101",
                        }
                    }]
                }]
            }
        })
        searcher.session.get = unittest.mock.Mock(side_effect=[
            requests.ConnectionError("PQAI DNS failure"),
            google_response,
        ])

        results = searcher.search("sample patent")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "A sample patent")
        self.assertEqual(results[0]["snippet"], "An … description")
        self.assertEqual(results[0]["year"], 2024)
        self.assertEqual(results[0]["url"], "https://patents.google.com/patent/US1234567A1")

    def test_common_plant_recognition_matches_reduce_originality_estimate(self):
        engine = GraphRAGEngine()
        concepts = [
            "plant recognition",
            "medicinal plant identification",
            "plant disease diagnosis",
            "image classification",
        ]
        results = [
            {
                "title": "Plant recognition using deep learning",
                "snippet": "Image classification for plant species identification.",
                "source": "arxiv",
                "keywords": ["plant", "recognition", "image classification"],
            },
            {
                "title": "Medicinal plant identification from leaf images",
                "snippet": "A method for medicinal plant recognition and classification.",
                "source": "crossref",
                "keywords": ["medicinal plant", "identification"],
            },
            {
                "title": "Plant disease recognition with convolutional networks",
                "snippet": "Classification of plant diseases from leaf images.",
                "source": "github",
                "keywords": ["plant disease", "recognition", "classification"],
            },
        ]

        with patch("cognigap.graphrag_engine.graph.get_concept_overlap_subgraph") as graph_scores:
            concept_overlaps = engine._compute_concept_overlaps(concepts, results)
        overlaps = engine._find_overlapping_works(concepts, results)
        score = engine._compute_originality_score(concept_overlaps, overlaps)

        graph_scores.assert_not_called()
        self.assertEqual(len(overlaps), 3)
        self.assertLess(score, 70)

    def test_no_relevant_search_evidence_does_not_claim_high_originality(self):
        engine = GraphRAGEngine()

        score = engine._compute_originality_score(
            [{"name": "plant recognition", "papers": 0, "patents": 0, "code": 0}],
            [],
        )

        self.assertIsNone(score)


if __name__ == "__main__":
    unittest.main()
