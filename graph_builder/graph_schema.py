"""
graph_schema.py
===============
Phase 1 — Applies all Neo4j constraints and indexes.
Run this once before ingestion. Safe to re-run (uses IF NOT EXISTS).
"""

import logging
import os
from neo4j import GraphDatabase

log = logging.getLogger("murphybot.schema")

# All node labels in the MurphyBot ontology
NODE_LABELS = [
    "Disease",
    "Symptom",
    "Sign",
    "Test",
    "Drug",
    "RiskFactor",
    "Complication",
    "BodySystem",
    "DemographicFactor",
    "SeverityLevel",
]

# Uniqueness constraints (CUI is the primary key for all medical entities)
CONSTRAINTS = [
    ("constraint_disease_cui",          "Disease",          "cui"),
    ("constraint_symptom_cui",          "Symptom",          "cui"),
    ("constraint_sign_cui",             "Sign",             "cui"),
    ("constraint_test_cui",             "Test",             "cui"),
    ("constraint_drug_cui",             "Drug",             "cui"),
    ("constraint_riskfactor_cui",       "RiskFactor",       "cui"),
    ("constraint_complication_cui",     "Complication",     "cui"),
    ("constraint_bodysystem_name",      "BodySystem",       "name"),
    ("constraint_demographic_value",    "DemographicFactor","value"),
    ("constraint_severity_level",       "SeverityLevel",    "level"),
]

# Full-text indexes for fuzzy name search
FULLTEXT_INDEXES = [
    ("ft_disease_names",   ["Disease"],   ["name", "aliases"]),
    ("ft_symptom_names",   ["Symptom"],   ["name", "aliases"]),
    ("ft_drug_names",      ["Drug"],      ["name", "aliases"]),
]


class Neo4jSchema:
    def __init__(self):
        uri  = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER",     "neo4j")
        pwd  = os.getenv("NEO4J_PASSWORD", "neo4j")
        self.driver = GraphDatabase.driver(uri, auth=(user, pwd))

    def apply_constraints(self):
        with self.driver.session() as session:
            # Uniqueness constraints
            for name, label, prop in CONSTRAINTS:
                cypher = (
                    f"CREATE CONSTRAINT {name} IF NOT EXISTS "
                    f"FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE"
                )
                session.run(cypher)
                log.info(f"  Constraint: {name}")

            # Standard indexes on name for fast lookups
            for label in NODE_LABELS:
                cypher = (
                    f"CREATE INDEX idx_{label.lower()}_name IF NOT EXISTS "
                    f"FOR (n:{label}) ON (n.name)"
                )
                session.run(cypher)
                log.info(f"  Index: idx_{label.lower()}_name")

            # Full-text indexes
            for idx_name, labels, props in FULLTEXT_INDEXES:
                label_str = "|".join(labels)
                prop_str  = ", ".join([f"n.{p}" for p in props])
                # Drop and recreate if exists (full-text indexes don't support IF NOT EXISTS in all versions)
                try:
                    session.run(f"DROP INDEX {idx_name} IF EXISTS")
                    session.run(
                        f"CREATE FULLTEXT INDEX {idx_name} "
                        f"FOR (n:{label_str}) ON EACH [{prop_str}]"
                    )
                    log.info(f"  Full-text index: {idx_name}")
                except Exception as e:
                    log.warning(f"  Full-text index {idx_name} skipped: {e}")

        log.info("All schema constraints and indexes applied.")

    def close(self):
        self.driver.close()
