"""
mcp_enrichment.py
=================
Orchestrator for all MCP enrichment on CONCLUSION state.
Single entry point called by consultation.py router.

Calls:
  - MCP: FDA drug info
  - RxNav: drug-drug interaction warnings
  - MCP: PubMed papers
  - MCP: Clinical guidelines
  - Claude: Confirmatory test list

All failures are non-blocking — partial results are always returned.
"""

import logging
from services.mcp.drug_enrichment import get_drug_suggestions, check_drug_interactions
from services.mcp.literature import get_papers_for_diagnosis
from services.mcp.guidelines import get_clinical_guidelines, get_confirmatory_tests
from services.mcp.mcp_client import is_mcp_available

log = logging.getLogger("murphybot.mcp_enrichment")


def _extract_top_diagnosis(triage_response: str) -> str:
    """
    Extract the primary diagnosis name from Claude's triage conclusion text.
    Looks for patterns like:
      '1. Acute Myocardial Infarction — High Confidence'
      '### 1. Acute Myocardial Infarction'
      '1. **Acute Myocardial Infarction**'
    """
    if not triage_response:
        return ""
    import re
    patterns = [
        r"(?:^|\n)\s*1[\.\)]\s+\*{0,2}([^—\n\*]+?)\*{0,2}\s*(?:—|-|–)",
        r"(?:^|\n)\s*#{1,4}\s*1[\.\)]\s+([^—\n]+?)(?:\s*—|\s*$)",
        r"(?:^|\n)\s*1[\.\)]\s+([A-Z][^—\n]{5,80})(?:\s*—|\s*\n)",
    ]
    for pattern in patterns:
        match = re.search(pattern, triage_response, re.MULTILINE)
        if match:
            name = match.group(1).strip().strip("*").strip()
            if len(name) > 4:
                return name
    return ""


def enrich_conclusion(
    diagnoses:           list[dict],
    symptoms:            list[str],
    current_medications: list[str] = None,
    user_profile:        dict = None,
    triage_response:     str = ""
) -> dict:
    """
    Full MCP enrichment pipeline. Called once on CONCLUSION state.

    Args:
        diagnoses:           graph_candidates from context assembler
        symptoms:            all_symptoms list
        current_medications: from user_profile (for interaction checking)
        user_profile:        full profile dict (optional)

    Returns:
        {
            "drugs":         list[dict],   ← FDA drug info
            "interactions":  list[dict],   ← RxNav warnings
            "pubmed_papers": list[dict],   ← top 3 PubMed papers
            "guidelines":    dict,         ← treatment + first aid
            "tests":         list[dict],   ← confirmatory tests (Claude)
            "mcp_available": bool          ← False if MCP server is down
        }
    """
    meds         = current_medications or []
    mcp_up       = is_mcp_available()
    result       = {
        "drugs":         [],
        "interactions":  [],
        "pubmed_papers": [],
        "guidelines":    {},
        "tests":         [],
        "mcp_available": mcp_up
    }

    if not diagnoses:
        return result

    
    top_disease = _extract_top_diagnosis(triage_response) or diagnoses[0]["disease"]

    # ── 1. FDA Drug Suggestions ───────────────────────────────────────────────
    try:
        if mcp_up:
            result["drugs"] = get_drug_suggestions(diagnoses)
            log.info(f"  Drug suggestions: {len(result['drugs'])} drugs")
        else:
            # Fallback: use drug names already in graph_candidates
            fallback_drugs = []
            for d in diagnoses[:2]:
                for drug_name in d.get("drugs", [])[:2]:
                    if drug_name:
                        fallback_drugs.append({
                            "name":      drug_name,
                            "available": False,
                            "note":      "FDA details unavailable — MCP server offline"
                        })
            result["drugs"] = fallback_drugs
    except Exception as e:
        log.warning(f"Drug suggestions failed: {e}")

    # ── 2. Drug Interaction Warnings (RxNav — works without MCP) ─────────────
    try:
        suggested_drug_names = [d["name"] for d in result["drugs"] if d.get("name")]
        if suggested_drug_names and meds:
            result["interactions"] = check_drug_interactions(
                suggested_drugs=suggested_drug_names,
                current_medications=meds
            )
            log.info(f"  Interactions found: {len(result['interactions'])}")
    except Exception as e:
        log.warning(f"Interaction check failed: {e}")

    # ── 3. PubMed Papers ──────────────────────────────────────────────────────
    try:
        if mcp_up:
            result["pubmed_papers"] = get_papers_for_diagnosis(diagnoses)
            log.info(f"  PubMed papers: {len(result['pubmed_papers'])}")
    except Exception as e:
        log.warning(f"PubMed search failed: {e}")

    # ── 4. Clinical Guidelines + First Aid ───────────────────────────────────
    try:
        if mcp_up:
            result["guidelines"] = get_clinical_guidelines(top_disease)
            log.info(f"  Guidelines fetched for: {top_disease}")
    except Exception as e:
        log.warning(f"Guidelines fetch failed: {e}")

    # ── 5. Confirmatory Tests (Claude — always available) ────────────────────
    try:
        result["tests"] = get_confirmatory_tests(diagnoses, symptoms)
        log.info(f"  Confirmatory tests: {len(result['tests'])}")
    except Exception as e:
        log.warning(f"Confirmatory tests failed: {e}")

    return result