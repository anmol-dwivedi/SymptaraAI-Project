"""
drug_enrichment.py
==================
Drug info from FDA OpenAPI (direct) + RxNav interactions (direct).
No MCP subprocess — calls the same APIs the MCP server wraps.
"""

import httpx
import logging

log     = logging.getLogger("murphybot.mcp.drugs")
TIMEOUT = 15

FDA_BASE   = "https://api.fda.gov/drug"
RXNAV_BASE = "https://rxnav.nlm.nih.gov/REST"


# ── FDA Drug Search ───────────────────────────────────────────────────────────
def search_drugs(drug_name: str) -> dict:
    """Search FDA drug label database directly."""
    try:
        url    = f"{FDA_BASE}/label.json"
        params = {"search": f"openfda.generic_name:{drug_name}", "limit": 1}
        r      = httpx.get(url, params=params, timeout=TIMEOUT)

        if r.status_code != 200:
            # Try brand name search as fallback
            params = {"search": f"openfda.brand_name:{drug_name}", "limit": 1}
            r      = httpx.get(url, params=params, timeout=TIMEOUT)

        if r.status_code != 200:
            return {"name": drug_name, "available": False}

        results = r.json().get("results", [])
        if not results:
            return {"name": drug_name, "available": False}

        label = results[0]
        openfda = label.get("openfda", {})
        return {
            "name":              drug_name,
            "available":         True,
            "brand_name":        openfda.get("brand_name", [drug_name])[0] if openfda.get("brand_name") else drug_name,
            "generic_name":      openfda.get("generic_name", [drug_name])[0] if openfda.get("generic_name") else drug_name,
            "indications":       _first(_truncate_list(label.get("indications_and_usage", []), 400)),
            "warnings":          _first(_truncate_list(label.get("warnings", []), 400)),
            "contraindications": _first(_truncate_list(label.get("contraindications", []), 300)),
            "dosage":            _first(_truncate_list(label.get("dosage_and_administration", []), 300)),
        }

    except Exception as e:
        log.warning(f"FDA search failed for {drug_name}: {e}")
        return {"name": drug_name, "available": False, "error": str(e)}


def get_drug_suggestions(diagnoses: list[dict]) -> list[dict]:
    """Get FDA drug info for top candidate diseases."""
    drug_names = []
    for d in diagnoses[:2]:
        drug_names.extend(d.get("drugs", [])[:2])

    seen, unique_drugs = set(), []
    for name in drug_names:
        if name and name.lower() not in seen:
            seen.add(name.lower())
            unique_drugs.append(name)

    return [search_drugs(name) for name in unique_drugs[:4]]


# ── RxNav Interactions ────────────────────────────────────────────────────────
def _get_rxcui(drug_name: str) -> str | None:
    """Convert drug name → RxCUI code."""
    try:
        r    = httpx.get(
            f"{RXNAV_BASE}/rxcui.json",
            params={"name": drug_name, "search": 1},
            timeout=TIMEOUT
        )
        data  = r.json()
        rxcuis = data.get("idGroup", {}).get("rxnormId", [])
        return rxcuis[0] if rxcuis else None
    except Exception as e:
        log.warning(f"RxCUI lookup failed for {drug_name}: {e}")
        return None


def check_drug_interactions(
    suggested_drugs:     list[str],
    current_medications: list[str]
) -> list[dict]:
    """Check interactions between suggested and current drugs via RxNav."""
    if not suggested_drugs or not current_medications:
        return []

    rxcui_map = {}
    for drug in suggested_drugs + current_medications:
        rxcui = _get_rxcui(drug)
        if rxcui:
            rxcui_map[drug] = rxcui

    if len(rxcui_map) < 2:
        return []

    try:
        rxcuis = " ".join(rxcui_map.values())
        r      = httpx.get(
            f"{RXNAV_BASE}/interaction/list.json",
            params={"rxcuis": rxcuis},
            timeout=TIMEOUT
        )
        if r.status_code != 200:
            return []
        data = r.json()
    except Exception as e:
        log.warning(f"RxNav interaction check failed: {e}")
        return []

    interactions   = []
    severity_order = {"high": 0, "moderate": 1, "low": 2, "unknown": 3}

    for group in data.get("fullInteractionTypeGroup", []):
        for itype in group.get("fullInteractionType", []):
            for pair in itype.get("interactionPair", []):
                concepts    = pair.get("interactionConcept", [])
                severity    = pair.get("severity", "unknown").lower()
                description = pair.get("description", "")

                if len(concepts) >= 2:
                    d1 = concepts[0].get("minConceptItem", {}).get("name", "")
                    d2 = concepts[1].get("minConceptItem", {}).get("name", "")

                    d1_sugg = any(s.lower() in d1.lower() for s in suggested_drugs)
                    d2_curr = any(s.lower() in d2.lower() for s in current_medications)
                    d1_curr = any(s.lower() in d1.lower() for s in current_medications)
                    d2_sugg = any(s.lower() in d2.lower() for s in suggested_drugs)

                    if (d1_sugg and d2_curr) or (d1_curr and d2_sugg):
                        interactions.append({
                            "drug_1":      d1,
                            "drug_2":      d2,
                            "severity":    severity,
                            "description": description
                        })

    interactions.sort(key=lambda x: severity_order.get(x["severity"], 3))
    return interactions


def _first(val):
    return val[0] if isinstance(val, list) and val else (val or "")

def _truncate_list(lst: list, max_chars: int) -> list:
    return [s[:max_chars] + "..." if len(s) > max_chars else s for s in lst]

def _truncate(text: str, max_chars: int) -> str:
    if not text: return ""
    return text[:max_chars] + "..." if len(text) > max_chars else text