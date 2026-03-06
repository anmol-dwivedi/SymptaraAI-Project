"""
neo4j_writer.py
===============
Phases 5 + 6 — Writes validated ExtractionResult objects to Neo4j.

Design principles:
  - MERGE on CUI (not name) to prevent duplicate nodes
  - All relationships carry evidence metadata
  - Weights (prevalence, typicality, severity) stored on edges
  - Never partial writes — all inserts in a single transaction per extraction
"""

import logging
import os
from typing import Dict, Any

from neo4j import GraphDatabase, Transaction

# from llm_extractor import ExtractionResult
from graph_builder.llm_extractor import ExtractionResult

log = logging.getLogger("murphybot.writer")

# Typicality string → numeric score
TYPICALITY_MAP = {"high": 0.9, "medium": 0.6, "low": 0.3}

# Sensitivity string → numeric score
SENSITIVITY_MAP = {"high": 0.85, "medium": 0.60, "low": 0.35}

# Frequency string → numeric score
FREQUENCY_MAP = {"common": 0.7, "uncommon": 0.3, "rare": 0.1}

# Urgency string → numeric score
URGENCY_MAP = {"stat": 1.0, "routine": 0.5, "elective": 0.2}

# Default prevalence when not specified (conservative)
DEFAULT_PREVALENCE = 0.5


class Neo4jWriter:
    def __init__(self):
        uri  = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER",     "neo4j")
        pwd  = os.getenv("NEO4J_PASSWORD", "neo4j")
        self.driver = GraphDatabase.driver(uri, auth=(user, pwd))
        log.info("Neo4j writer connected.")

    def write_extraction(self, extraction: ExtractionResult, chunk: Dict[str, Any]):
        """Write a full extraction to Neo4j in a single transaction."""
        with self.driver.session() as session:
            session.execute_write(self._write_tx, extraction, chunk)

    def _write_tx(self, tx: Transaction, extraction: ExtractionResult, chunk: Dict):
        meta = {
            "source_book":    chunk["source_book"],
            "chapter":        chunk["chapter"],
            "section_title":  chunk["section_title"],
            "chunk_id":       chunk["chunk_id"],
            "evidence_text":  extraction.evidence_text,
        }

        # ── Disease node ──────────────────────────────────────────────────
        disease_cui  = extraction.disease.cui or f"NOCUI_{extraction.disease.name.replace(' ', '_')}"
        disease_name = extraction.disease.name

        tx.run("""
            MERGE (d:Disease {cui: $cui})
            ON CREATE SET d.name=$name, d.aliases=[$name], d.source_count=1, d.created_at=datetime()
            ON MATCH  SET d.source_count = coalesce(d.source_count, 0) + 1,
                          d.aliases = CASE WHEN NOT $name IN d.aliases
                                      THEN d.aliases + [$name]
                                      ELSE d.aliases END
        """, cui=disease_cui, name=disease_name)

        # ── Symptoms ──────────────────────────────────────────────────────
        for s in extraction.symptoms:
            cui  = s.cui or f"NOCUI_{s.name.replace(' ', '_')}"
            typ  = TYPICALITY_MAP.get(s.typicality, 0.6)
            tx.run("""
                MERGE (sym:Symptom {cui: $cui})
                ON CREATE SET sym.name=$name, sym.aliases=[$name]
                ON MATCH  SET sym.aliases = CASE WHEN NOT $name IN sym.aliases
                                            THEN sym.aliases + [$name]
                                            ELSE sym.aliases END
                WITH sym
                MATCH (d:Disease {cui: $disease_cui})
                MERGE (d)-[r:HAS_SYMPTOM]->(sym)
                SET r.prevalence_score  = coalesce(r.prevalence_score, $prev),
                    r.typicality_score  = $typ,
                    r.severity_weight   = coalesce(r.severity_weight, 3.0),
                    r.evidence_text     = $evidence,
                    r.source_book       = $source_book,
                    r.chapter           = $chapter,
                    r.chunk_id          = $chunk_id
            """, cui=cui, name=s.name, disease_cui=disease_cui,
                 prev=DEFAULT_PREVALENCE, typ=typ,
                 **meta)

            # Reverse edge for probabilistic reasoning (Phase 7)
            tx.run("""
                MATCH (sym:Symptom {cui: $sym_cui})
                MATCH (d:Disease   {cui: $disease_cui})
                MERGE (sym)-[r:INCREASES_LIKELIHOOD_OF]->(d)
                SET r.likelihood_ratio = $typ,
                    r.source_book      = $source_book,
                    r.chunk_id         = $chunk_id
            """, sym_cui=cui, disease_cui=disease_cui, typ=typ, **meta)

        # ── Signs ─────────────────────────────────────────────────────────
        for s in extraction.signs:
            cui  = s.cui or f"NOCUI_{s.name.replace(' ', '_')}"
            sens = SENSITIVITY_MAP.get(s.sensitivity, 0.6)
            tx.run("""
                MERGE (sg:Sign {cui: $cui})
                ON CREATE SET sg.name=$name, sg.aliases=[$name]
                WITH sg
                MATCH (d:Disease {cui: $disease_cui})
                MERGE (d)-[r:HAS_SIGN]->(sg)
                SET r.sensitivity   = $sens,
                    r.evidence_text = $evidence,
                    r.source_book   = $source_book,
                    r.chunk_id      = $chunk_id
            """, cui=cui, name=s.name, disease_cui=disease_cui,
                 sens=sens, **meta)

        # ── Tests ─────────────────────────────────────────────────────────
        for t in extraction.tests:
            cui     = t.cui or f"NOCUI_{t.name.replace(' ', '_')}"
            urgency = URGENCY_MAP.get(t.urgency, 0.5)
            tx.run("""
                MERGE (te:Test {cui: $cui})
                ON CREATE SET te.name=$name, te.aliases=[$name]
                WITH te
                MATCH (d:Disease {cui: $disease_cui})
                MERGE (d)-[r:REQUIRES_TEST]->(te)
                SET r.urgency       = $urgency,
                    r.evidence_text = $evidence,
                    r.source_book   = $source_book,
                    r.chunk_id      = $chunk_id
                WITH d, te
                MERGE (te)-[rc:CONFIRMS]->(d)
                SET rc.source_book = $source_book,
                    rc.chunk_id    = $chunk_id
            """, cui=cui, name=t.name, disease_cui=disease_cui,
                 urgency=urgency, **meta)

        # ── Risk Factors ──────────────────────────────────────────────────
        for rf in extraction.risk_factors:
            cui = rf.cui or f"NOCUI_{rf.name.replace(' ', '_')}"
            tx.run("""
                MERGE (r:RiskFactor {cui: $cui})
                ON CREATE SET r.name=$name, r.aliases=[$name]
                WITH r
                MATCH (d:Disease {cui: $disease_cui})
                MERGE (d)-[rel:ASSOCIATED_WITH]->(r)
                SET rel.odds_ratio_approx = $odds,
                    rel.evidence_text     = $evidence,
                    rel.source_book       = $source_book,
                    rel.chunk_id          = $chunk_id
            """, cui=cui, name=rf.name, disease_cui=disease_cui,
                 odds=rf.odds_ratio_approx, **meta)

        # ── Complications ─────────────────────────────────────────────────
        for c in extraction.complications:
            cui  = c.cui or f"NOCUI_{c.name.replace(' ', '_')}"
            freq = FREQUENCY_MAP.get(c.frequency, 0.3)
            tx.run("""
                MERGE (co:Complication {cui: $cui})
                ON CREATE SET co.name=$name, co.aliases=[$name]
                WITH co
                MATCH (d:Disease {cui: $disease_cui})
                MERGE (d)-[r:HAS_COMPLICATION]->(co)
                SET r.frequency     = $freq,
                    r.evidence_text = $evidence,
                    r.source_book   = $source_book,
                    r.chunk_id      = $chunk_id
            """, cui=cui, name=c.name, disease_cui=disease_cui,
                 freq=freq, **meta)

        # ── Drugs ─────────────────────────────────────────────────────────
        for dr in extraction.drugs:
            cui = dr.cui or f"NOCUI_{dr.name.replace(' ', '_')}"
            tx.run("""
                MERGE (drug:Drug {cui: $cui})
                ON CREATE SET drug.name=$name, drug.aliases=[$name]
                WITH drug
                MATCH (d:Disease {cui: $disease_cui})
                MERGE (drug)-[r:TREATS]->(d)
                SET r.first_line    = $first_line,
                    r.evidence_text = $evidence,
                    r.source_book   = $source_book,
                    r.chunk_id      = $chunk_id
            """, cui=cui, name=dr.name, disease_cui=disease_cui,
                 first_line=dr.first_line, **meta)

        # ── Body Systems ──────────────────────────────────────────────────
        for bs in extraction.body_systems:
            tx.run("""
                MERGE (sys:BodySystem {name: $name})
                WITH sys
                MATCH (d:Disease {cui: $disease_cui})
                MERGE (d)-[:AFFECTS]->(sys)
            """, name=bs, disease_cui=disease_cui)

        # ── Demographics ──────────────────────────────────────────────────
        for demo in extraction.demographics:
            value = f"{demo.type}:{demo.value}"
            tx.run("""
                MERGE (df:DemographicFactor {value: $value})
                ON CREATE SET df.type=$type, df.label=$label
                WITH df
                MATCH (d:Disease {cui: $disease_cui})
                MERGE (d)-[r:COMMON_IN]->(df)
                SET r.note      = $note,
                    r.chunk_id  = $chunk_id
            """, value=value, type=demo.type, label=demo.value,
                 disease_cui=disease_cui, note=demo.note,
                 chunk_id=chunk["chunk_id"])

    def close(self):
        self.driver.close()
        log.info("Neo4j writer closed.")
