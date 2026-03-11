"""
llm_extractor.py
================
Phase 4 — Layer B: LLM structured relationship extraction.

Takes a chunk + NER entity candidates, calls GPT-4o-mini,
returns a validated ExtractionResult or None on failure.

Key design decisions:
  - Entity list from Layer A is injected into the prompt (grounds the LLM)
  - Pydantic validates the JSON schema — no partial writes to Neo4j
  - Retries up to 2 times on invalid JSON
  - Logs failed chunks to failed_chunks.jsonl for manual review
"""

import json
import logging
import os
from pathlib import Path
from typing import List, Optional, Dict, Any

from openai import OpenAI
from pydantic import BaseModel, Field, field_validator
from tenacity import retry, stop_after_attempt, wait_exponential

log = logging.getLogger("murphybot.llm")

EXTRACTION_MODEL = os.getenv("LLM_EXTRACTION_MODEL", "gpt-4o-mini")
FAILED_LOG = Path("failed_chunks.jsonl")

# ── Pydantic schemas ────────────────────────────────────────────────────────

class EntityRef(BaseModel):
    cui:  Optional[str] = None
    name: str

class SymptomRef(EntityRef):
    typicality: str = Field(default="medium", pattern="^(high|medium|low)$")

class SignRef(EntityRef):
    sensitivity: str = Field(default="medium", pattern="^(high|medium|low)$")

class TestRef(EntityRef):
    urgency: str = Field(default="routine", pattern="^(stat|routine|elective)$")

class RiskFactorRef(EntityRef):
    odds_ratio_approx: Optional[float] = None

class ComplicationRef(EntityRef):
    frequency: str = Field(default="common", pattern="^(common|uncommon|rare)$")

class DrugRef(EntityRef):
    first_line: bool = False

class DemographicRef(BaseModel):
    type:  str   # "age", "sex", "ethnicity"
    value: str   # "elderly", "male", "female", etc.
    note:  Optional[str] = None

class ExtractionResult(BaseModel):
    disease:        EntityRef
    symptoms:       List[SymptomRef]      = []
    signs:          List[SignRef]         = []
    tests:          List[TestRef]         = []
    risk_factors:   List[RiskFactorRef]   = []
    complications:  List[ComplicationRef] = []
    drugs:          List[DrugRef]         = []
    body_systems:   List[str]             = []
    demographics:   List[DemographicRef]  = []
    evidence_text:  str

    @field_validator("evidence_text")
    @classmethod
    def evidence_not_empty(cls, v):
        if not v or len(v.strip()) < 20:
            raise ValueError("evidence_text must be a non-trivial sentence from the source")
        return v.strip()

    @field_validator("disease")
    @classmethod
    def disease_has_name(cls, v):
        if not v.name or len(v.name.strip()) < 2:
            raise ValueError("disease.name must be present")
        return v


# ── Prompt template ─────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a medical knowledge graph extractor. Your task is to extract
structured medical relationships from a clinical textbook section.

RULES (strictly enforced):
1. Only extract relationships explicitly stated in the text. Never infer or hallucinate.
2. Use ONLY entities from the CANDIDATE ENTITIES list when possible. Do not invent new entity names.
3. If a candidate entity has a CUI, include it in the output. Otherwise set cui to null.
4. Return ONLY a JSON object. No markdown, no explanation, no code fences.
5. If the text does not describe a specific disease, return {"disease": {"name": "SKIP"}, "evidence_text": "No disease described"}.
6. evidence_text must be a verbatim sentence (or close paraphrase) from the source text that supports the extraction.

OUTPUT JSON SCHEMA:
{
  "disease":       {"cui": string|null, "name": string},
  "symptoms":      [{"cui": string|null, "name": string, "typicality": "high|medium|low"}],
  "signs":         [{"cui": string|null, "name": string, "sensitivity": "high|medium|low"}],
  "tests":         [{"cui": string|null, "name": string, "urgency": "stat|routine|elective"}],
  "risk_factors":  [{"cui": string|null, "name": string, "odds_ratio_approx": float|null}],
  "complications": [{"cui": string|null, "name": string, "frequency": "common|uncommon|rare"}],
  "drugs":         [{"cui": string|null, "name": string, "first_line": boolean}],
  "body_systems":  [string],
  "demographics":  [{"type": string, "value": string, "note": string|null}],
  "evidence_text": string
}"""

USER_PROMPT_TEMPLATE = """SECTION METADATA:
Book: {source_book}
Chapter: {chapter}
Section: {section_title}

CANDIDATE ENTITIES (from NER — use these names and CUIs where possible):
{entity_list}

SECTION TEXT:
{chunk_text}

Extract the medical knowledge graph relationships. Return JSON only."""


# ── Extractor class ─────────────────────────────────────────────────────────

class LLMExtractor:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model  = EXTRACTION_MODEL
        log.info(f"LLM extractor ready. Model: {self.model}")

    def extract(
        self,
        chunk: Dict[str, Any],
        candidate_entities: List[Dict],
    ) -> Optional[ExtractionResult]:
        """
        Call LLM to extract relationships from a chunk.
        Returns validated ExtractionResult or None.
        """
        entity_list = self._format_entity_list(candidate_entities)
        user_msg = USER_PROMPT_TEMPLATE.format(
            source_book   = chunk["source_book"],
            chapter       = chunk["chapter"],
            section_title = chunk["section_title"],
            entity_list   = entity_list,
            chunk_text    = chunk["text"][:4000],   # hard cap to avoid token overflow
        )

        raw_json = self._call_llm(user_msg)
        if raw_json is None:
            self._log_failed(chunk, "LLM call failed after retries")
            return None

        return self._validate(raw_json, chunk)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    def _call_llm(self, user_msg: str) -> Optional[str]:
        response = self.client.chat.completions.create(
            model      = self.model,
            temperature= 0.0,           # deterministic
            max_tokens = 1500,
            messages   = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_msg},
            ],
        )
        return response.choices[0].message.content.strip()

    def _validate(self, raw_json: str, chunk: Dict) -> Optional[ExtractionResult]:
        # Strip markdown fences if LLM added them despite instructions
        raw_json = raw_json.strip().lstrip("```json").lstrip("```").rstrip("```").strip()

        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as e:
            log.warning(f"JSON parse error: {e}")
            self._log_failed(chunk, f"JSON parse error: {e}", raw_json)
            return None

        # Skip chunks where LLM found no disease
        if data.get("disease", {}).get("name") == "SKIP":
            return None

        try:
            result = ExtractionResult(**data)
        except Exception as e:
            log.warning(f"Schema validation error: {e}")
            self._log_failed(chunk, f"Validation error: {e}", raw_json)
            return None

        return result

    def _format_entity_list(self, entities: List[Dict]) -> str:
        if not entities:
            return "(none detected)"
        lines = []
        for e in entities:
            cui_str = e["cui"] or "no CUI"
            lines.append(f"  - [{e['entity_type']}] {e['canonical_name']} (CUI: {cui_str}, from: '{e['surface_form']}')")
        return "\n".join(lines)

    def _log_failed(self, chunk: Dict, reason: str, raw: str = ""):
        entry = {
            "chunk_id":      chunk.get("chunk_id"),
            "source_book":   chunk.get("source_book"),
            "section_title": chunk.get("section_title"),
            "reason":        reason,
            "raw_llm":       raw[:500] if raw else "",
        }
        with open(FAILED_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
