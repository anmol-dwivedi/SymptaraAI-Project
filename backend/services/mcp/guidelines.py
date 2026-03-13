"""
guidelines.py
=============
Clinical guidelines via NIH MedlinePlus API (direct, free).
Claude generates structured confirmatory test list.
"""

import httpx
import json
import logging
import re
import xml.etree.ElementTree as ET
import anthropic
from config import settings

log    = logging.getLogger("murphybot.mcp.guidelines")
client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
TIMEOUT = 15


def get_clinical_guidelines(disease_name: str) -> dict:
    """Fetch clinical guidelines via NLM health topics search."""

    # Primary: NLM health topics full-text search
    try:
        r = httpx.get(
            "https://wsearch.nlm.nih.gov/ws/query",
            params={
                "db":     "healthTopics",
                "term":   disease_name,
                "retmax": 1
            },
            timeout=TIMEOUT
        )
        if r.status_code == 200 and r.text:
            root     = ET.fromstring(r.text)
            contents = []
            for content in root.findall(".//content"):
                name = content.get("name", "")
                text = "".join(content.itertext()).strip()
                if name not in ("title", "organizationName") and text:
                    contents.append(text)

            snippet = " ".join(contents)
            snippet = re.sub(r"<[^>]+>", " ", snippet).strip()
            snippet = re.sub(r"\s+", " ", snippet)

            if snippet:
                return {
                    "disease":   disease_name,
                    "guideline": snippet[:800],
                    "source":    "NLM Health Topics"
                }
    except Exception as e:
        log.warning(f"NLM search failed for {disease_name}: {e}")

    # Fallback: MedlinePlus Connect
    try:
        r = httpx.get(
            "https://connect.medlineplus.gov/application",
            params={
                "mainSearchCriteria.v.cs": "2.16.840.1.113883.6.90",
                "mainSearchCriteria.v.dn": disease_name,
                "knowledgeResponseType":   "application/json"
            },
            timeout=TIMEOUT
        )
        if r.status_code == 200:
            data    = r.json()
            entry   = data.get("feed", {}).get("entry", [])
            if entry:
                summary = entry[0].get("summary", {})
                content = summary.get("_value", "") if isinstance(summary, dict) else str(summary)
                content = re.sub(r"<[^>]+>", " ", content).strip()
                content = re.sub(r"\s+", " ", content)
                if content:
                    return {
                        "disease":   disease_name,
                        "guideline": content[:800] + "..." if len(content) > 800 else content,
                        "source":    "NIH MedlinePlus"
                    }
    except Exception as e:
        log.warning(f"MedlinePlus failed for {disease_name}: {e}")

    return {"disease": disease_name, "guideline": "", "source": ""}


def get_confirmatory_tests(
    diagnoses: list[dict],
    symptoms:  list[str]
) -> list[dict]:
    """Claude generates structured confirmatory test list."""
    if not diagnoses:
        return []

    top_diseases = [d["disease"] for d in diagnoses[:3]]
    response     = client.messages.create(
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
            "content": (
                f"Symptoms: {', '.join(symptoms)}\n"
                f"Candidate diagnoses: {', '.join(top_diseases)}"
            )
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
        log.warning("Failed to parse confirmatory tests JSON")

    return []