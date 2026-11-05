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
from cognigap.config import get_available_llm_providers, get_llm_provider


# ═══════════════════════════════════════════════════════════
# LLM API Calls (with automatic failover)
# ═══════════════════════════════════════════════════════════

def _call_gemini(prompt, api_key):
    """Call Google Gemini API with fallback models."""
    models_to_try = [
        "gemini-2.5-flash",
        "gemini-flash-latest",
        "gemini-2.5-flash-lite",
        "gemini-pro-latest",
    ]
    last_err = None
    for model in models_to_try:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2048}
            }
            resp = requests.post(url, json=payload, timeout=25)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "")
            else:
                last_err = f"HTTP {resp.status_code}: {resp.text[:120]}"
        except Exception as e:
            last_err = str(e)
    raise RuntimeError(f"Gemini error: {last_err}")


def _call_openai(prompt, api_key):
    """Call OpenAI API."""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3, "max_tokens": 2048,
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=25)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _call_groq(prompt, api_key):
    """Call Groq API trying available fast open-weights models."""
    models_to_try = [
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "qwen/qwen3.8-27b",
    ]
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    last_err = None
    for model in models_to_try:
        try:
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3, "max_tokens": 2048,
            }
            resp = requests.post(url, json=payload, headers=headers, timeout=25)
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            else:
                last_err = f"HTTP {resp.status_code}: {resp.text[:120]}"
        except Exception as e:
            last_err = str(e)
    raise RuntimeError(f"Groq error: {last_err}")


def _call_llm(prompt):
    """
    Call any configured LLM with automatic failover waterfall:
    Tries each configured provider in sequence (Gemini -> Groq -> OpenAI).
    Whichever one works first is used. If one fails (e.g. rate limit, quota),
    it automatically fails over to the next without failing the user's request.
    """
    providers = get_available_llm_providers()
    if not providers:
        logger.info("  No LLM API keys configured. Using deterministic ontology generator.")
        return None

    last_errors = []
    for provider, key in providers:
        try:
            logger.info(f"  Attempting query expansion via [{provider}]...")
            if provider == "gemini":
                result = _call_gemini(prompt, key)
            elif provider == "groq":
                result = _call_groq(prompt, key)
            elif provider == "openai":
                result = _call_openai(prompt, key)
            else:
                continue

            if result and result.strip():
                logger.info(f"  ✓ Successfully received expansion from [{provider}]")
                return result
        except Exception as e:
            err_msg = f"{provider} failed ({e})"
            logger.warning(f"  ✗ {err_msg} -> Rolling over to next available LLM...")
            last_errors.append(err_msg)

    logger.warning("  All configured LLM providers failed or were rate-limited. Falling back to heuristic expansion.")
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
