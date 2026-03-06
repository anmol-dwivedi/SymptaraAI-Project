# MurphyBot — Project Context File v2
> Paste this at the start of every new Claude conversation to restore full project context instantly.
> Update the "Current Status" section every time you complete a phase.

---

## What Is MurphyBot?
A Conversational Medical Diagnostic Assistant with two modes:
- **Mental Health Buddy** — empathetic chat for emotional support. Prompt-engineering driven, no RAG.
- **Consultation Mode** — advanced symptom triage assistant. Works like a doctor honing into a diagnosis
  through follow-up questions. Returns 2-4 ranked differential diagnoses with confidence levels.

**Core MVP behavior:** The triage system asks follow-up questions when symptoms are insufficient,
then converges on 2-4 ranked diagnoses when it has enough context. It never dumps a diagnosis
immediately — it earns it through a conversation.

---

## Developer Profile
- Python proficient, some ML/data science, backend/API experience
- Learning: RAG, GraphRAG, Hybrid retrieval, LLM APIs, agents, embeddings, observability
- Target role: Associate AI Engineer
- Machine: AMD Ryzen 7 4800H, 16 threads, 15GB RAM, Ubuntu 24.04.3 LTS, no dedicated GPU

---

## Tech Stack (Locked)

| Layer | Technology | Reason |
|-------|-----------|--------|
| Knowledge Graph | Neo4j (local) + PrimeKG subgraph | Pre-built, peer-reviewed disease-symptom graph. No overnight pipeline needed. |
| Vector DB | ChromaDB (local) | Zero infra, runs in-process with FastAPI. 16 books + HPO terms. |
| Embeddings | OpenAI text-embedding-3-small | Best quality/cost ratio for embeddings |
| LLM Reasoning | Anthropic Claude (claude-sonnet-4) | Multi-turn conversation, vision for X-rays, structured outputs |
| Backend | FastAPI | Python-native, async |
| Frontend | Lovable (AI-generated UI) | Fastest path to shippable demo |
| User Data | Supabase (Postgres + Auth + RLS) | User profiles, sessions, messages, uploaded files |
| Observability | LangSmith | Trace every LLM call from day 1 |
| Doc ingestion | Docling (already done) | 16 books parsed to .md files |

**NOT in MVP:** PrimeKG genomic/protein nodes, fine-tuning, travel history,
Emergency SOS (build last — it's just a frontend button)

---

## Architecture Overview

```
USER INPUT (text + optional image/PDF/voice)
        ↓
INPUT PROCESSOR
  • Image/X-ray → Claude vision → text description
  • PDF → extract text
  • Voice → Web Speech API → text
        ↓
SYMPTOM EXTRACTOR (Claude structured call)
  Free text → ["fever", "stiff neck", "photophobia"]
        ↓
HPO MAPPER (Hybrid)
  Step 1: Claude maps symptoms → HPO IDs (high confidence terms)
  Step 2: Vector similarity fallback for low-confidence/unusual terms
  Output: [HP:0001945, HP:0031360, HP:0000613]
        ↓
HYBRID RETRIEVAL
  Neo4j (PrimeKG):  HPO IDs → ranked candidate diseases (top 10)
  ChromaDB (books): symptom text → relevant clinical chunks (top 5)
        ↓
CONTEXT ASSEMBLER
  Graph results + vector chunks + user profile (Supabase) + conversation history
        ↓
TRIAGE CONTROLLER (Claude, 3-state system prompt)
  State 1 GATHERING  (<3 symptoms)     → ask ONE follow-up question
  State 2 NARROWING  (6+ candidates)   → ask ONE differentiating question
  State 3 CONCLUSION (≤5 candidates OR 4+ rounds) → return 2-4 ranked diagnoses
        ↓
RESPONSE to user
```

**Key architectural decision:** State transitions are controlled by Python logic (symptom count,
graph result count, conversation turns). Claude executes the state — Python controls the flow.
This keeps behavior predictable and debuggable.

---

## PrimeKG Subgraph — What We Load

Full PrimeKG = 129k nodes. We load only:

| Node Type | Approx Count | Include? |
|-----------|-------------|---------|
| Disease | ~17k | ✅ Yes |
| Symptom/Phenotype (HPO) | ~9k | ✅ Yes |
| Drug | ~8k | ✅ Yes (treatment suggestions) |
| Biological process | ~28k | ❌ No — too molecular |
| Gene/Protein | ~60k | ❌ No — not needed for triage |

Result: ~34k nodes, loads in minutes, queries in milliseconds.

**HPO Mapping note:** PrimeKG disease-symptom edges use HPO term IDs (e.g. HP:0001945 = fever).
User's natural language symptoms must be mapped to HPO IDs before graph query.
We embed all ~9k HPO terms into a separate ChromaDB collection for vector fallback.

---

## ChromaDB Collections

| Collection | Contents | Embedding source |
|-----------|---------|-----------------|
| `medical_books` | 16 medical books chunked at H2 headings (~1200 tokens) | text-embedding-3-small |
| `hpo_terms` | All ~9k HPO phenotype terms + descriptions | text-embedding-3-small |

---

## Supabase Schema

```sql
user_profiles (
  user_id, age, sex, blood_type,
  allergies text[],
  chronic_conditions text[],
  current_medications text[],
  past_surgeries text[]
)

sessions (
  session_id, user_id, created_at,
  status,           -- 'active' | 'concluded'
  final_diagnoses jsonb
)

messages (
  message_id, session_id, role,   -- 'user' | 'assistant'
  content, created_at,
  extracted_symptoms text[],
  hpo_terms text[]
)

session_files (
  file_id, session_id,
  file_type,        -- 'xray' | 'pdf' | 'image'
  storage_path,
  claude_analysis text
)
```

---

## Repository File Structure (Target)

```
murphybot/
├── MURPHYBOT_CONTEXT.md            ← THIS FILE
├── .env
├── docling_output/                 ← 16 parsed .md files ✅ DONE
│
├── data_pipeline/
│   ├── load_primekg.py             ← Download PrimeKG CSVs → filter → Neo4j
│   ├── embed_books.py              ← Chunk .md files → ChromaDB medical_books
│   ├── embed_hpo.py                ← Embed HPO terms → ChromaDB hpo_terms
│   └── verify_data.py              ← Sanity check queries on both DBs
│
├── backend/
│   ├── main.py                     ← FastAPI app
│   ├── routers/
│   │   ├── chat.py                 ← Mental Health Buddy
│   │   └── consultation.py         ← Consultation Mode / Triage
│   ├── services/
│   │   ├── symptom_extractor.py    ← Claude call: free text → symptom list
│   │   ├── hpo_mapper.py           ← Hybrid: Claude + ChromaDB → HPO IDs
│   │   ├── graph_service.py        ← Neo4j Cypher: HPO IDs → candidate diseases
│   │   ├── vector_service.py       ← ChromaDB: symptom text → clinical chunks
│   │   ├── context_assembler.py    ← Merge all sources into prompt context
│   │   ├── triage_controller.py    ← 3-state logic + Claude reasoning call
│   │   └── memory_service.py       ← Supabase session read/write
│   └── models/
│       └── schemas.py              ← Pydantic request/response models
│
└── frontend/                       ← Lovable-generated
```

---

## Triage State Logic (Python-controlled)

```python
def determine_triage_state(symptoms: list, graph_results: list, turn_count: int) -> str:
    if len(symptoms) < 3:
        return "GATHERING"
    if len(graph_results) > 5 and turn_count < 4:
        return "NARROWING"
    return "CONCLUSION"
```

---

## System Prompt Templates (3 States)

**GATHERING:**
```
You are MurphyBot, a careful medical triage assistant.
You have collected {n} symptoms so far: {symptom_list}
User profile: {age}, {sex}, {conditions}

You need more information to narrow down the diagnosis.
Ask ONE specific, targeted clinical question. Do not speculate yet.
Keep it conversational — like a doctor, not a form.
```

**NARROWING:**
```
You are MurphyBot. Based on the symptoms {symptom_list}, the knowledge graph
suggests these candidate conditions: {candidate_diseases}

Ask ONE question that best differentiates between the top candidates.
Focus on the symptom or sign that would most change your ranking.
```

**CONCLUSION:**
```
You are MurphyBot. Based on all gathered information:
Symptoms: {symptom_list}
User: {age}, {sex}, {medical_history}
Knowledge graph candidates: {graph_results}
Clinical reference: {vector_chunks}
Uploaded files analysis: {file_analysis}

Provide 2-4 ranked differential diagnoses. For each:
1. Condition name + confidence (High/Medium/Low)
2. Key symptoms supporting this diagnosis
3. What makes it rank above/below others
4. Recommended next steps (tests, specialist, urgency)
5. Red flag symptoms that would require emergency care

End with: "This is not a medical diagnosis. Please consult a doctor."
```

---

## Day-by-Day Build Plan

### Day 1 — Data Layer (no LLM calls, ~$1-2 embedding cost)
- [ ] Download PrimeKG CSVs from https://github.com/mims-harvard/PrimeKG
- [ ] Run `load_primekg.py` — filter to Disease+Symptom+Drug → Neo4j
- [ ] Run `embed_books.py` — 16 .md files → ChromaDB medical_books collection
- [ ] Run `embed_hpo.py` — HPO terms → ChromaDB hpo_terms collection
- [ ] Run `verify_data.py` — test queries on both DBs

### Day 2 — Backend
- [ ] FastAPI scaffold + .env config + LangSmith setup
- [ ] Supabase schema creation + user profile endpoints
- [ ] symptom_extractor.py (Claude structured call)
- [ ] hpo_mapper.py (hybrid: Claude + vector fallback)
- [ ] graph_service.py (Neo4j Cypher triage query)
- [ ] vector_service.py (ChromaDB retrieval)
- [ ] context_assembler.py (merge all sources)
- [ ] triage_controller.py (3-state logic + Claude call)
- [ ] Test full triage flow in Postman

### Day 3 — Frontend + Deploy
- [ ] Mental Health Buddy endpoint (simple system prompt)
- [ ] Lovable frontend wired to backend
- [ ] File upload → Claude vision
- [ ] Deploy FastAPI on Railway
- [ ] Smoke test end-to-end

---

## Consultation Mode Features

| Feature | Implementation | Status |
|---------|---------------|--------|
| Symptom triage w/ follow-up Qs | 3-state triage controller | ⬜ |
| 2-4 ranked diagnoses | CONCLUSION state output | ⬜ |
| User medical profile context | Supabase → context assembler | ⬜ |
| PrimeKG graph retrieval | Neo4j Cypher + HPO mapping | ⬜ |
| Book knowledge retrieval | ChromaDB semantic search | ⬜ |
| X-ray / image upload | Claude vision API | ⬜ |
| PDF upload | Text extraction → context | ⬜ |
| Session memory | Supabase messages table | ⬜ |
| Nearby doctors | Google Places API | ⬜ |
| "Explain like a noob" | Prompt toggle | ⬜ |
| LangSmith tracing | From day 1 | ⬜ |
| Emergency SOS | Frontend button only | ⬜ |

## Mental Health Buddy Features

| Feature | Status |
|---------|--------|
| Empathetic chat persona | ⬜ |
| Crisis detection + resource redirect | ⬜ |
| Session memory | ⬜ |

---

## Key Design Decisions

**Why PrimeKG over custom graph from books?**
PrimeKG is pre-built, peer-reviewed, loads in minutes. Custom graph from books requires
overnight pipeline + SciSpacy NER setup + LLM extraction (~$3 + 8 hours). PrimeKG gives
us a better graph faster. Books go into vector DB for nuanced clinical context instead.

**Why Python controls triage state (not the LLM)?**
LLMs are non-deterministic. If you let the LLM decide when to conclude, it may conclude
too early or ask too many questions. Python state logic is predictable, debuggable,
and testable. Claude executes each state — Python decides which state.

**Why Hybrid HPO mapping?**
LLM handles common clinical terms perfectly (fever, headache, nausea).
Vector similarity handles unusual phrasings, patient language, and rare symptoms
without burning LLM tokens every time. HPO terms pre-embedded once at startup.

**Why ChromaDB over Pinecone/pgvector?**
Portfolio MVP. No cloud account needed, zero latency, runs in same process as FastAPI.
Migration to Pinecone for production is a 30-minute swap. Shows you understand
the tradeoff between local-dev and production infrastructure.

---

## .env Template

```
# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# OpenAI (embeddings only)
OPENAI_API_KEY=sk-...

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=MurphyBot2025!

# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...

# LangSmith
LANGCHAIN_API_KEY=ls__...
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=murphybot

# App
CHROMA_PATH=./chroma_db
MD_FOLDER=./docling_output
```

---

## Current Status
```
✅ 16 medical books parsed to .md via Docling
✅ Architecture finalized (Hybrid RAG: PrimeKG + ChromaDB)
✅ Tech stack locked
⬜ Neo4j setup + PrimeKG subgraph loaded
⬜ ChromaDB medical_books collection embedded
⬜ ChromaDB hpo_terms collection embedded
⬜ Data layer verified
⬜ FastAPI backend scaffold
⬜ Symptom extractor service
⬜ HPO mapper service (hybrid)
⬜ Graph service (Neo4j triage query)
⬜ Vector service (ChromaDB retrieval)
⬜ Context assembler
⬜ Triage controller (3-state)
⬜ Supabase schema + user profiles
⬜ LangSmith tracing
⬜ Mental Health Buddy endpoint
⬜ Lovable frontend
⬜ File upload + Claude vision
⬜ Deployed on Railway
```

---

## How to Use This File
1. After each work session: tick off completed items in Current Status
2. Starting a new Claude chat: upload or paste this file as first message
3. Say what you just completed and what you want to work on next

---
*Last updated: 2026-03-01 — Architecture pivot complete. Moving from custom GraphRAG
to Hybrid RAG (PrimeKG subgraph + ChromaDB vector search). Ready to start Day 1 data layer.*
