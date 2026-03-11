"""
triage_query.py
===============
Phase 7 — Triage algorithm: graph traversal scoring.

Standalone script to test your knowledge graph once built.

Usage:
    python triage_query.py --symptoms "fever,cough" --age elderly --sex male
    python triage_query.py --symptoms "chest pain,diaphoresis" --top 5
"""

import argparse
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()


TRIAGE_CYPHER = """
MATCH (s:Symptom)
WHERE toLower(s.name) IN $symptom_names
   OR any(alias IN s.aliases WHERE toLower(alias) IN $symptom_names)
MATCH (s)<-[r:HAS_SYMPTOM]-(d:Disease)
OPTIONAL MATCH (d)-[:COMMON_IN]->(demo:DemographicFactor)
  WHERE demo.value IN $demographics
WITH d,
     SUM(
       coalesce(r.prevalence_score, 0.5) *
       coalesce(r.typicality_score, 0.5) *
       coalesce(r.severity_weight, 3.0)
     ) AS base_score,
     COUNT(s) AS matched_count,
     COLLECT(DISTINCT s.name) AS matched_symptoms,
     CASE WHEN COUNT(demo) > 0 THEN 1.2 ELSE 1.0 END AS demo_modifier,
     COLLECT(DISTINCT r.source_book) AS sources
WITH d,
     (base_score * demo_modifier) AS score,
     matched_count,
     matched_symptoms,
     sources
RETURN d.name          AS disease,
       round(score, 3) AS score,
       matched_count,
       matched_symptoms,
       sources
ORDER BY score DESC
LIMIT $top_n
"""

REASONING_CYPHER = """
MATCH (d:Disease) WHERE toLower(d.name) = toLower($disease_name)
OPTIONAL MATCH (d)-[rs:HAS_SYMPTOM]->(s:Symptom)
OPTIONAL MATCH (d)-[rt:REQUIRES_TEST]->(t:Test)
OPTIONAL MATCH (d)-[rc:HAS_COMPLICATION]->(c:Complication)
OPTIONAL MATCH (drug:Drug)-[rd:TREATS]->(d)
OPTIONAL MATCH (d)-[:AFFECTS]->(bs:BodySystem)
RETURN d.name AS disease,
       COLLECT(DISTINCT {name: s.name, typicality: rs.typicality_score, evidence: rs.evidence_text}) AS symptoms,
       COLLECT(DISTINCT {name: t.name, urgency: rt.urgency, evidence: rt.evidence_text})             AS tests,
       COLLECT(DISTINCT {name: c.name, frequency: rc.frequency})                                     AS complications,
       COLLECT(DISTINCT {name: drug.name, first_line: rd.first_line})                                AS drugs,
       COLLECT(DISTINCT bs.name)                                                                      AS body_systems
"""


def run_triage(symptoms: list, demographics: list, top_n: int = 5):
    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "neo4j")),
    )

    symptom_names = [s.strip().lower() for s in symptoms]

    with driver.session() as session:
        print(f"\n{'='*60}")
        print(f"  TRIAGE — Symptoms: {', '.join(symptoms)}")
        if demographics:
            print(f"  Demographics: {', '.join(demographics)}")
        print(f"{'='*60}\n")

        results = session.run(
            TRIAGE_CYPHER,
            symptom_names=symptom_names,
            demographics=demographics,
            top_n=top_n,
        )

        rows = list(results)
        if not rows:
            print("  No matching diseases found. Check your graph has been populated.")
            return

        for i, row in enumerate(rows, 1):
            print(f"  #{i}  {row['disease']}")
            print(f"       Score:    {row['score']}")
            print(f"       Matched:  {', '.join(row['matched_symptoms'])}")
            print(f"       Sources:  {', '.join(set(row['sources']))}")
            print()

        # Full reasoning chain for top disease
        top_disease = rows[0]["disease"]
        print(f"\n{'─'*60}")
        print(f"  REASONING CHAIN — {top_disease}")
        print(f"{'─'*60}\n")

        chain = session.run(REASONING_CYPHER, disease_name=top_disease).single()
        if chain:
            if chain["symptoms"]:
                print("  Symptoms supporting this diagnosis:")
                for s in chain["symptoms"]:
                    if s["name"]:
                        typ = f"(typicality: {s['typicality']})" if s["typicality"] else ""
                        print(f"    • {s['name']} {typ}")

            if chain["tests"]:
                print("\n  Recommended tests:")
                for t in chain["tests"]:
                    if t["name"]:
                        urg = f"[{t['urgency']}]" if t["urgency"] else ""
                        print(f"    • {t['name']} {urg}")

            if chain["complications"]:
                print("\n  Potential complications if missed:")
                for c in chain["complications"]:
                    if c["name"]:
                        print(f"    ⚠ {c['name']}")

            if chain["drugs"]:
                print("\n  Treatment options:")
                for d in chain["drugs"]:
                    if d["name"]:
                        fl = " [first-line]" if d["first_line"] else ""
                        print(f"    • {d['name']}{fl}")

    driver.close()
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MurphyBot Triage Query")
    parser.add_argument("--symptoms",     required=True, help="Comma-separated symptoms, e.g. 'fever,cough'")
    parser.add_argument("--age",          default="",    help="Age group: elderly|adult|child|infant")
    parser.add_argument("--sex",          default="",    help="Sex: male|female")
    parser.add_argument("--top",          type=int, default=5, help="Number of top diseases to return")
    args = parser.parse_args()

    symptoms     = [s.strip() for s in args.symptoms.split(",")]
    demographics = [v for v in [args.age, args.sex] if v]

    run_triage(symptoms, demographics, args.top)
