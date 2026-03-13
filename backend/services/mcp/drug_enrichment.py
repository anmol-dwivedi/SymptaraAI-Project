"""
drug_enrichment.py
==================
Drug suggestions from FDA (via MCP) + drug-drug interaction
warnings from NIH RxNav (direct API, no key needed).
"""

import httpx
import logging
from services.mcp.mcp_client import call_tool

log = logging.getLogger("murphybot.mcp.drugs")

RXNAV_BASE  = "https://rxnav.nlm.nih.gov/REST"
RXNORM_BASE = "https://rxnav.nlm.nih.gov/REST"
TIMEOUT     = 10


# ── FDA Drug Search ───────────────────────────────────────────────────────────
def search_drugs(drug_name: str) -> dict:
    """
    Search FDA database for a drug by name.
    Returns label info: uses, warnings, dosage, contraindications.
    """
    result = call_tool("search-drugs", {
        "query": drug_name,
        "limit": 1
    })

    if "error" in result:
        return {"name": drug_name, "available": False, "error": result["error"]}

    # Extract the most useful fields from FDA label
    results = result.get("results", [])
    if not results:
        return {"name": drug_name, "available": False}

    drug = results[0]
    return {
        "name":              drug_name,
        "available":         True,
        "brand_name":        drug.get("brand_name", ""),
        "generic_name":      drug.get("generic_name", ""),
        "indications":       _truncate(drug.get("indications_and_usage", ""), 400),
        "warnings":          _truncate(drug.get("warnings", ""), 400),
        "contraindications": _truncate(drug.get("contraindications", ""), 300),
        "dosage":            _truncate(drug.get("dosage_and_administration", ""), 300),
    }


def get_drug_suggestions(diagnoses: list[dict]) -> list[dict]:
    """
    Get FDA drug info for top candidate diseases.
    Uses the drugs already pulled from Neo4j graph in graph_candidates.

    Args:
        diagnoses: graph_candidates from context assembler
                   each has a "drugs" key with drug name list

    Returns:
        List of enriched drug dicts with FDA label data
    """
    drug_names = []
    for d in diagnoses[:2]:  # top 2 diseases only
        drug_names.extend(d.get("drugs", [])[:2])  # top 2 drugs per disease

    # Deduplicate
    seen = set()
    unique_drugs = []
    for name in drug_names:
        if name and name.lower() not in seen:
            seen.add(name.lower())
            unique_drugs.append(name)

    enriched = []
    for drug_name in unique_drugs[:4]:  # cap at 4 total
        info = search_drugs(drug_name)
        enriched.append(info)

    return enriched


# ── RxNav Drug Interaction Checker ────────────────────────────────────────────
def _get_rxcui(drug_name: str) -> str | None:
    """Convert drug name to RxCUI code using RxNorm API."""
    try:
        url = f"{RXNORM_BASE}/rxcui.json"
        r   = httpx.get(url, params={"name": drug_name}, timeout=TIMEOUT)
        data = r.json()
        rxcui = data.get("idGroup", {}).get("rxnormId", [])
        return rxcui[0] if rxcui else None
    except Exception as e:
        log.warning(f"RxCUI lookup failed for {drug_name}: {e}")
        return None


def check_drug_interactions(
    suggested_drugs: list[str],
    current_medications: list[str]
) -> list[dict]:
    """
    Check for interactions between suggested drugs and user's current medications
    using NIH RxNav Interaction API (free, no key needed).

    Args:
        suggested_drugs:     drugs suggested by diagnosis e.g. ["Ceftriaxone"]
        current_medications: from user_profile.current_medications e.g. ["Warfarin"]

    Returns:
        [
            {
                "drug_1":      "Warfarin",
                "drug_2":      "Aspirin",
                "severity":    "high",
                "description": "Increased risk of bleeding"
            },
            ...
        ]
    """
    if not suggested_drugs or not current_medications:
        return []

    all_drugs  = suggested_drugs + current_medications
    rxcui_map  = {}

    # Get RxCUI for all drugs
    for drug in all_drugs:
        rxcui = _get_rxcui(drug)
        if rxcui:
            rxcui_map[drug] = rxcui

    if len(rxcui_map) < 2:
        return []

    # Call RxNav interaction API with all RxCUIs
    rxcuis = list(rxcui_map.values())
    try:
        url = f"{RXNAV_BASE}/interaction/list.json"
        r   = httpx.get(url, params={"rxcuis": " ".join(rxcuis)}, timeout=TIMEOUT)
        data = r.json()
    except Exception as e:
        log.warning(f"RxNav interaction check failed: {e}")
        return []

    interactions = []
    full_interactions = data.get("fullInteractionTypeGroup", [])

    for group in full_interactions:
        for interaction_type in group.get("fullInteractionType", []):
            for pair in interaction_type.get("interactionPair", []):
                concepts    = pair.get("interactionConcept", [])
                severity    = pair.get("severity", "unknown").lower()
                description = pair.get("description", "")

                if len(concepts) >= 2:
                    drug_1 = concepts[0].get("minConceptItem", {}).get("name", "")
                    drug_2 = concepts[1].get("minConceptItem", {}).get("name", "")

                    # Only flag if one drug is suggested and one is current medication
                    d1_suggested = any(d.lower() in drug_1.lower() for d in suggested_drugs)
                    d2_current   = any(d.lower() in drug_2.lower() for d in current_medications)
                    d1_current   = any(d.lower() in drug_1.lower() for d in current_medications)
                    d2_suggested = any(d.lower() in drug_2.lower() for d in suggested_drugs)

                    if (d1_suggested and d2_current) or (d1_current and d2_suggested):
                        interactions.append({
                            "drug_1":      drug_1,
                            "drug_2":      drug_2,
                            "severity":    severity,
                            "description": description
                        })

    # Sort by severity: high first
    severity_order = {"high": 0, "moderate": 1, "low": 2, "unknown": 3}
    interactions.sort(key=lambda x: severity_order.get(x["severity"], 3))

    return interactions


def _truncate(text: str, max_chars: int) -> str:
    if not text:
        return ""
    text = text.strip()
    return text[:max_chars] + "..." if len(text) > max_chars else text