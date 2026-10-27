"""
CogniGap — LLM Query Expansion Engine
=======================================
Translates informal, jargon-heavy student project descriptions into
standardized, formal technical queries suitable for academic and patent search.

Uses Gemini API (primary), OpenAI, or Groq as LLM backends.
Also extracts key concepts for the knowledge graph.
"""

import json
import re
import requests
from chronos.utils import logger
from cognigap.config import get_llm_provider


# ═══════════════════════════════════════════════════════════
# LLM API Calls
# ═══════════════════════════════════════════════════════════

def _call_gemini(prompt, api_key):
    """Call Google Gemini API."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2048}
    }
    resp = requests.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    candidates = data.get("candidates", [])
    if candidates:
        parts = candidates[0].get("content", {}).get("parts", [])
        if parts:
            return parts[0].get("text", "")
    return ""


def _call_openai(prompt, api_key):
    """Call OpenAI API."""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3, "max_tokens": 2048,
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _call_groq(prompt, api_key):
    """Call Groq API."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3, "max_tokens": 2048,
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _call_llm(prompt):
    """Call the configured LLM provider."""
    provider, key = get_llm_provider()
    if not provider:
        logger.warning("No LLM API key configured. Using fallback expansion.")
        return None

    try:
        if provider == "gemini":
            return _call_gemini(prompt, key)
        elif provider == "openai":
            return _call_openai(prompt, key)
        elif provider == "groq":
            return _call_groq(prompt, key)
    except Exception as e:
        logger.error(f"LLM API call failed ({provider}): {e}")
        return None


# ═══════════════════════════════════════════════════════════
# Query Expansion
# ═══════════════════════════════════════════════════════════

EXPANSION_PROMPT = """You are an expert academic research librarian. A student has described their project idea in informal, everyday language. Your task is to:

1. **Translate** the informal description into 3-5 formal, technical queries suitable for searching academic databases (ArXiv, Semantic Scholar) and patent databases. Use standardized terminology from computer science, engineering, and AI literature.

2. **Extract** 4-7 key technical concepts/components that form the architecture of this idea.

3. **Identify** 2-4 gaps — areas where the proposed idea might be novel or under-explored.

Student's project idea:
\"\"\"
{idea}
\"\"\"

Respond in this EXACT JSON format (no markdown, no code blocks):
{{
  "expanded_queries": [
    "formal academic query 1",
    "formal academic query 2",
    "formal academic query 3"
  ],
  "concepts": [
    "technical concept 1",
    "technical concept 2",
    "technical concept 3"
  ],
  "gaps": [
    "potential novelty area 1",
    "potential novelty area 2"
  ],
  "formal_summary": "A 2-3 sentence formal description of the project using proper academic terminology."
}}"""


def expand_query(idea_text):
    """
    Translate an informal project description into formal technical queries,
    extract concepts, and identify potential gaps.

    Args:
        idea_text: The student's informal project description.

    Returns:
        dict with keys: expanded_queries, concepts, gaps, formal_summary
    """
    logger.info("  ── LLM Query Expansion Engine ──")

    if not idea_text or len(idea_text.strip()) < 10:
        logger.warning("  Idea text too short for expansion")
        return _fallback_expansion(idea_text)

    prompt = EXPANSION_PROMPT.format(idea=idea_text)
    response = _call_llm(prompt)

    if not response:
        logger.info("  LLM unavailable, using fallback expansion")
        return _fallback_expansion(idea_text)

    try:
        # Try to extract JSON from the response
        result = _parse_json_response(response)
        if result:
            logger.info(f"  Expanded into {len(result.get('expanded_queries', []))} queries, "
                       f"{len(result.get('concepts', []))} concepts")
            return result
    except Exception as e:
        logger.error(f"  Failed to parse LLM response: {e}")

    return _fallback_expansion(idea_text)


def _parse_json_response(text):
    """Extract JSON from LLM response (handles markdown code blocks)."""
    # Remove markdown code block wrappers if present
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r'^```(?:json)?\s*\n?', '', text)
        text = re.sub(r'\n?```\s*$', '', text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON in the text
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None


def _fallback_expansion(idea_text):
    """
    Fallback query expansion using keyword extraction when LLM is unavailable.
    Still provides meaningful queries by restructuring the input.
    """
    from chronos.utils import extract_words

    words = extract_words(idea_text or "")
    # Build formal-sounding queries from extracted keywords
    queries = []
    if len(words) >= 4:
        queries.append(f"{' '.join(words[:4])} system architecture")
        queries.append(f"{' '.join(words[:3])} machine learning approach")
        queries.append(f"{' '.join(words[1:5])} prior art survey")
    elif words:
        queries.append(f"{' '.join(words)} technical implementation")

    concepts = words[:7] if words else ["general"]
    gaps = ["unique implementation approach", "novel combination of techniques"]

    return {
        "expanded_queries": queries or [idea_text[:100]],
        "concepts": concepts,
        "gaps": gaps,
        "formal_summary": idea_text[:300] if idea_text else "",
    }


if __name__ == "__main__":
    # Test the query expansion
    test_idea = (
        "I want to build an app that checks if my project idea already exists. "
        "It should search through research papers and GitHub repos and tell me "
        "what parts are original and what parts already exist."
    )
    result = expand_query(test_idea)
    print(json.dumps(result, indent=2))
