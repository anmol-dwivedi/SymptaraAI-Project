"""
guidelines.py
=============
Clinical guidelines (first aid + treatment protocols) via MCP.
Claude generates the structured confirmatory test list.
"""

import json
import logging
import anthropic
from config import settings
from services.mcp.mcp_client import call_tool

log    = logging.getLogger("murphybot.mcp.guidelines")
client = anthropic.Anthropic(api_key=settings.anthropic_api_key)


# ── Clinical Guidelines via MCP ───────────────────────────────────────────────
def get_clinical_guidelines(disease_name: str) -> dict:
    """
    Fetch clinical guidelines for a disease via MCP.
    Returns first aid and treatment protocol text.

    Args:
        disease_name: e.g. "Bacterial Meningitis"

    Returns:
        {
            "disease":   "Bacterial Meningitis",
            "guideline": "...",   ← treatment protocol text
            "source":    "..."    ← e.g. "CDC Clinical Guidelines"
        }
    """
    result = call_tool("search-clinical-guidelines", {
        "query": f"{disease_name} treatment guidelines first aid management"
    })

    if "error" in result:
        log.warning(f"Guidelines fetch failed: {result['error']}")
        return {
            "disease":   disease_name,
            "guideline": "",
            "source":    ""
        }

    guidelines = result.get("guidelines", result.get("results", []))
    if not guidelines:
        return {"disease": disease_name, "guideline": "", "source": ""}

    top = guidelines[0]
    return {
        "disease":   disease_name,
        "guideline": _truncate(
            top.get("content", top.get("text", top.get("guideline", ""))), 800
        ),
        "source":    top.get("source", top.get("organization", ""))
    }


# ── Confirmatory Tests via Claude ─────────────────────────────────────────────
def get_confirmatory_tests(
    diagnoses: list[dict],
    symptoms:  list[str]
) -> list[dict]:
    """
    Claude generates a structured list of confirmatory tests for the top diagnoses.
    More reliable than parsing guideline text for a clean structured output.

    Args:
        diagnoses: top graph_candidates
        symptoms:  all_symptoms from context

    Returns:
        [
            {
                "test":     "Lumbar Puncture + CSF Analysis",
                "urgency":  "STAT",
                "purpose":  "Differentiates bacterial vs viral meningitis",
                "for_disease": "Bacterial Meningitis"
            },
            ...
        ]
    """
    if not diagnoses:
        return []

    top_diseases = [d["disease"] for d in diagnoses[:3]]
    symptom_str  = ", ".join(symptoms)
    disease_str  = ", ".join(top_diseases)

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=600,
        system="""You are a clinical diagnostic assistant.
Given symptoms and candidate diagnoses, return a structured list of confirmatory tests.
Return ONLY a JSON array, no explanation, no markdown.

Each item must have:
- test: full test name
- urgency: STAT | Urgent | Routine
- purpose: one sentence why this test
- for_disease: which diagnosis this confirms

Order by urgency (STAT first). Maximum 6 tests.""",
        messages=[{
            "role": "user",
            "content": f"Symptoms: {symptom_str}\nCandidate diagnoses: {disease_str}"
        }]
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        tests = json.loads(raw)
        if isinstance(tests, list):
            return tests
    except json.JSONDecodeError:
        log.warning("Failed to parse confirmatory tests JSON from Claude")

    return []


def _truncate(text: str, max_chars: int) -> str:
    if not text:
        return ""
    text = text.strip()
    return text[:max_chars] + "..." if len(text) > max_chars else text