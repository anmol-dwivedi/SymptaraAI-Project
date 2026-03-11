"""
ner_layer.py
============
Phase 4 — Layer A: Deterministic SciSpacy NER.

Uses en_ner_bc5cdr_md (Disease + Chemical NER) with:
  - AbbreviationDetector: expands MI → Myocardial infarction
  - UMLS EntityLinker: maps each entity to a CUI
  - Confidence threshold filtering (default 0.85)

Output: list of dicts with keys: surface_form, cui, canonical_name, entity_type, score
"""

import logging
import os
from typing import List, Dict, Optional

import spacy
import scispacy  # noqa: F401 — registers scispacy components
from scispacy.abbreviation import AbbreviationDetector
from scispacy.linking import EntityLinker

log = logging.getLogger("murphybot.ner")

UMLS_THRESHOLD = float(os.getenv("UMLS_CONFIDENCE_THRESHOLD", "0.85"))

# BC5CDR label → MurphyBot node type mapping
LABEL_MAP = {
    "DISEASE":  "Disease",
    "CHEMICAL": "Drug",      # BC5CDR uses CHEMICAL for drugs/chemicals
}


class SciSpacyNER:
    """
    Wraps the SciSpacy NER pipeline.
    Loads models once at init — reuse across all chunks.
    """

    def __init__(self):
        log.info("Loading SciSpacy NER pipeline (this may take 30–60 seconds on first run)...")
        log.info("If UMLS linker not cached, first run will download ~1GB. Please wait.")

        # Load BC5CDR NER model
        self.nlp = spacy.load("en_ner_bc5cdr_md")

        # Add abbreviation resolver BEFORE entity linker
        self.nlp.add_pipe("abbreviation_detector")

        # Add UMLS entity linker — downloads KB on first use, then caches
        self.nlp.add_pipe(
            "scispacy_linker",
            config={
                "resolve_abbreviations": True,
                "linker_name": "umls",
                "filter_for_definitions": False,   # keep all CUIs, we filter by score
                "no_definition_threshold": 0.70,   # lower than our threshold to get candidates
                "max_entities_per_mention": 3,     # top 3 candidates per mention
            },
        )
        self.linker = self.nlp.get_pipe("scispacy_linker")
        log.info("SciSpacy NER pipeline ready.")

    def extract(self, text: str) -> List[Dict]:
        """
        Run NER on text, link to UMLS, return filtered entity list.

        Returns:
            List of dicts: {surface_form, cui, canonical_name, entity_type, score}
        """
        doc = self.nlp(text)
        entities = []
        seen_cuis = set()

        for ent in doc.ents:
            entity_type = LABEL_MAP.get(ent.label_, None)
            if entity_type is None:
                continue  # skip labels we don't handle

            # Get UMLS candidates
            kb_ents = ent._.kb_ents
            if not kb_ents:
                # No UMLS link — still include as surface form with no CUI
                entity = {
                    "surface_form":   ent.text,
                    "cui":            None,
                    "canonical_name": ent.text,
                    "entity_type":    entity_type,
                    "score":          0.0,
                }
                entities.append(entity)
                continue

            # Pick the best candidate above threshold
            best_cui, best_score = self._best_candidate(kb_ents)
            if best_score < UMLS_THRESHOLD:
                continue  # below confidence threshold — skip

            if best_cui in seen_cuis:
                continue  # deduplicate within this chunk
            seen_cuis.add(best_cui)

            canonical_name = self._canonical_name(best_cui)

            entities.append({
                "surface_form":   ent.text,
                "cui":            best_cui,
                "canonical_name": canonical_name,
                "entity_type":    entity_type,
                "score":          round(best_score, 3),
            })

        return entities

    def _best_candidate(self, kb_ents) -> tuple:
        """Return (cui, score) of highest-scoring candidate."""
        best_cui, best_score = None, 0.0
        for cui, score in kb_ents:
            if score > best_score:
                best_cui, best_score = cui, score
        return best_cui, best_score

    def _canonical_name(self, cui: str) -> str:
        """Look up the preferred UMLS name for a CUI."""
        try:
            entity_data = self.linker.kb.cui_to_entity.get(cui)
            if entity_data:
                return entity_data.canonical_name
        except Exception:
            pass
        return cui  # fallback to CUI string

    def close(self):
        pass  # spacy models don't need explicit cleanup
