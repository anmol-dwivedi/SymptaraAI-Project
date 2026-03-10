from neo4j import GraphDatabase
from langsmith import traceable
from config import settings

driver = GraphDatabase.driver(
    settings.neo4j_uri,
    auth=(settings.neo4j_user, settings.neo4j_password)
)


def _run_query(cypher: str, params: dict) -> list:
    with driver.session() as session:
        result = session.run(cypher, params)
        return [record.data() for record in result]


TRIAGE_QUERY = """
MATCH (p:Phenotype)-[:ASSOCIATED_WITH]-(d:Disease)
WHERE p.hpo_id IN $hpo_ids
WITH d,
     count(DISTINCT p) AS matched_symptoms,
     collect(DISTINCT p.name) AS matched_names
ORDER BY matched_symptoms DESC
LIMIT $limit
RETURN
    d.name     AS disease,
    d.node_id  AS disease_id,
    matched_symptoms,
    matched_names
"""

DISEASE_DETAIL_QUERY = """
MATCH (d:Disease {node_id: $disease_id})-[:ASSOCIATED_WITH]-(p:Phenotype)
RETURN
    d.name          AS disease,
    collect(p.name) AS all_symptoms
"""

DRUG_QUERY = """
MATCH (drug:Drug)-[:INDICATED_FOR]->(d:Disease {node_id: $disease_id})
RETURN drug.name AS drug_name
LIMIT 5
"""


@traceable(name="graph-triage-query")
def query_diseases_by_hpo(hpo_ids: list[str], limit: int = 10) -> list[dict]:
    if not hpo_ids:
        return []

    # Strip "HP:" prefix — PrimeKG stores bare numeric IDs e.g. "1945" not "HP:0001945"
    # Also strip leading zeros: "0001945" → "1945"
    cleaned = [h.replace("HP:", "").lstrip("0") or "0" for h in hpo_ids]

    # print(f"  DEBUG cleaned HPO IDs: {cleaned}")

    raw = _run_query(TRIAGE_QUERY, {"hpo_ids": cleaned, "limit": limit})

    # print(f"  DEBUG raw from neo4j: {raw[:2] if raw else 'EMPTY'}")

    enriched = []
    for row in raw:
        detail = get_disease_detail(row["disease_id"])
        total_known = len(detail.get("all_symptoms", [])) or 1
        row["match_ratio"] = round(row["matched_symptoms"] / total_known, 3)
        enriched.append(row)

    return enriched


@traceable(name="graph-disease-detail")
def get_disease_detail(disease_id: str) -> dict:
    results = _run_query(DISEASE_DETAIL_QUERY, {"disease_id": disease_id})
    return results[0] if results else {"disease": "", "all_symptoms": []}


@traceable(name="graph-drug-lookup")
def get_drugs_for_disease(disease_id: str) -> list[str]:
    results = _run_query(DRUG_QUERY, {"disease_id": disease_id})
    return [r["drug_name"] for r in results]


def get_top_candidates(hpo_ids: list[str], top_n: int = 5) -> list[dict]:
    candidates = query_diseases_by_hpo(hpo_ids, limit=top_n * 2)
    for c in candidates:
        c["drugs"] = get_drugs_for_disease(c["disease_id"])
    return candidates[:top_n]


def close():
    driver.close()