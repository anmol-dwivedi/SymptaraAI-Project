# MurphyBot — MVP Execution Roadmap
> Version: Final | Ready to Build
> Stack: PrimeKG + ChromaDB + Claude + FastAPI + Lovable + Supabase + Google Places + Medical MCP

---

## What We Are Building

**Mode 1 — Mental Health Buddy**
Empathetic chat. No RAG. Pure prompt engineering with crisis detection.

**Mode 2 — Consultation Mode (The Core)**
1. Takes symptoms (text / voice / image / PDF)
2. Asks intelligent follow-up questions until context is sufficient
3. Returns 2-4 ranked differential diagnoses
4. Suggests nearby specialist doctors (Google Places)
5. Enriches with FDA drug info + PubMed evidence (Medical MCP)

---

## Architecture

```
USER INPUT (text / image / PDF / voice)
        ↓
INPUT PROCESSOR
(vision→text, PDF→text, voice→text)
        ↓
SYMPTOM EXTRACTOR  [Claude call #1]
"fever and stiff neck" → ["fever", "neck stiffness"]
        ↓
HPO MAPPER (Hybrid)
Claude → common terms → HP:xxxxxxx
ChromaDB fallback → unusual/vague terms
        ↓
HYBRID RETRIEVAL
  Neo4j PrimeKG:  HPO IDs → top 10 candidate diseases
  ChromaDB books: symptom text → top 5 clinical chunks
        ↓
CONTEXT ASSEMBLER
graph + chunks + user profile + history + files
        ↓
TRIAGE CONTROLLER  [Claude call #2]
GATHERING / NARROWING / CONCLUSION
        ↓
IF CONCLUSION →
  Google Places → nearby specialists
  Medical MCP   → FDA info + PubMed papers
        ↓
RESPONSE
```

---

## Triage State Machine (Python controls state)

```python
def get_triage_state(symptoms, graph_results, turn_count):
    if len(symptoms) < 3:
        return "GATHERING"
    if len(graph_results) > 5 and turn_count < 4:
        return "NARROWING"
    return "CONCLUSION"
```

Claude executes each state. Python decides which state. This keeps behavior predictable.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Knowledge Graph | Neo4j + PrimeKG subgraph (Disease+Symptom+Drug ~34k nodes) |
| Vector DB | ChromaDB local (medical_books + hpo_terms collections) |
| Embeddings | OpenAI text-embedding-3-small |
| LLM | Anthropic Claude claude-sonnet-4 (reasoning + vision) |
| Backend | FastAPI |
| User Data | Supabase (Postgres + Auth + RLS) |
| Doctor Finder | Google Places API (your Colab code, ported) |
| Medical Evidence | JamesANZ Medical MCP (FDA + PubMed) |
| Observability | LangSmith (every Claude call traced from day 1) |
| Frontend | Lovable |
| Deploy | Railway (backend) |

---

## Repository Structure

```
murphybot/
├── MURPHYBOT_CONTEXT.md
├── MURPHYBOT_ROADMAP.md
├── .env
├── docling_output/           ← 16 .md files DONE
├── data_pipeline/
│   ├── load_primekg.py
│   ├── embed_books.py
│   ├── embed_hpo.py
│   └── verify_data.py
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── routers/
│   │   ├── chat.py           ← Mental Health Buddy
│   │   ├── consultation.py   ← Triage endpoint
│   │   └── profile.py        ← User profile CRUD
│   └── services/
│       ├── symptom_extractor.py
│       ├── hpo_mapper.py
│       ├── graph_service.py
│       ├── vector_service.py
│       ├── context_assembler.py
│       ├── triage_controller.py
│       ├── memory_service.py
│       ├── doctor_finder.py
│       └── mcp_enrichment.py
├── medical-mcp/              ← git clone JamesANZ/medical-mcp
└── frontend/                 ← Lovable generated
```

---

## DAY 1 — Data Layer
Goal: Neo4j + ChromaDB populated and verified. ~$2 cost. No LLM reasoning calls.

### PrimeKG to Neo4j (~3 hours)
1. Download PrimeKG CSVs from Harvard Dataverse
   https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/IXA7BM
   Files needed: nodes.csv, edges.csv
2. Run load_primekg.py
   Filter: keep only Disease, Phenotype, Drug nodes and their edges
   Load into Neo4j with MERGE on node ID
   Create indexes on HPO term ID and node type
   Expected: ~34k nodes, ~500k edges, ~15 minutes to load
3. Verify with Cypher test query:
   MATCH (p:Phenotype) WHERE p.name IN ["Fever", "Headache"]
   MATCH (p)<-[:HAS_PHENOTYPE]-(d:Disease)
   RETURN d.name, count(p) as matched ORDER BY matched DESC LIMIT 10

### ChromaDB Ingestion (~2 hours, runs unattended)
4. Run embed_books.py
   Reuse md_parser.py H2 chunking logic
   Embed with text-embedding-3-small
   Store in collection: medical_books
   Expected: ~5000 chunks, ~45 mins, ~$1.50
5. Run embed_hpo.py
   Download HPO ontology from https://hpo.jax.org/data/ontology
   Extract: term ID + name + definition per phenotype
   Embed and store in collection: hpo_terms
   Expected: ~9000 terms, ~10 mins, ~$0.30

### Verify (~30 mins)
6. Run verify_data.py
   Test 1: Neo4j triage query with known HPO IDs
   Test 2: ChromaDB book search for "fever headache stiff neck"
   Test 3: HPO vector lookup for "splitting headache worse in morning"
   All 3 must return sensible results before moving to Day 2.

---

## DAY 2 — Backend
Goal: Full triage pipeline working end to end. Testable in Postman.

### Morning: Scaffold (~2 hours)
1. pip install fastapi uvicorn anthropic openai chromadb neo4j supabase langsmith googlemaps python-dotenv pydantic pymupdf
2. main.py + config.py — env vars, CORS, router registration
3. Supabase: run schema SQL, enable RLS, test connection
4. LangSmith: wrap every Claude call with @traceable decorator

### Midday: Core Services (~3 hours)
5. symptom_extractor.py — Claude structured call: free text → symptom list
6. hpo_mapper.py — Claude maps known terms, ChromaDB fallback for vague ones
7. graph_service.py — Neo4j Cypher: HPO IDs → ranked candidate diseases
8. vector_service.py — ChromaDB: symptom text → top 5 clinical book chunks

### Afternoon: Orchestration (~3 hours)
9.  context_assembler.py — merges graph + chunks + profile + history + files
10. triage_controller.py — 3-state Python logic + Claude call
11. memory_service.py — Supabase read/write for sessions and messages
12. consultation.py router — single POST /consultation/message endpoint

### Evening: Post-Diagnosis (~2 hours)
13. doctor_finder.py — port your working Colab code directly
    Fires only on CONCLUSION state
    Uses user browser coords (lat/lng passed with request)
    Returns top 5 doctors: name, address, rating, Maps link

14. mcp_enrichment.py — Medical MCP integration
    git clone https://github.com/JamesANZ/medical-mcp
    cd medical-mcp && npm install && npm run build
    Run as subprocess on localhost:3000
    After CONCLUSION: call search-medical-literature (top 3 PubMed papers)
    After CONCLUSION: call search-drugs (FDA info on suggested meds)

Day 2 done when Postman shows this flow:
  Turn 1: "fever and headache" → bot asks about neck stiffness
  Turn 2: "yes stiff neck" → bot asks about light sensitivity
  Turn 3: "yes light hurts" → 2-4 diagnoses + nearby doctors + PubMed

---

## DAY 3 — Frontend + Deploy
Goal: Live public URL. Demo-ready.

### Morning (~2 hours)
15. chat.py router — Mental Health Buddy
    Claude with empathetic persona system prompt
    Crisis keyword detection → resource redirection
    Session memory via Supabase

16. File upload handling
    Image/X-ray: base64 → Claude vision → text description injected into context
    PDF: PyMuPDF text extraction → injected into context

### Midday: Lovable Frontend (~3 hours)
17. Generate UI in Lovable using this prompt:
    "Build a dark medical assistant UI called MurphyBot.
     Two modes via top tabs: Chat Mode and Consultation Mode.
     Consultation Mode: left panel = chat, right panel = file upload drag-drop area.
     Top bar: red Emergency SOS button, Report button, Location indicator.
     Bottom tabs: Drugs/Dosage, Medical Tests, Doctors Nearby, First Aid,
     Easy Explanation, References/Citations.
     Input bar with mic icon and send button.
     Chat Mode: warm full-width chat, soft colors."
18. Wire to backend: replace mock calls with Railway URL

### Afternoon: Deploy (~2 hours)
19. railway login && railway init && railway up
    Add all env vars in Railway dashboard
    Verify all services connect (Neo4j local note: use ngrok or migrate to Neo4j AuraDB free tier)
20. End-to-end smoke test on live URL

### Evening: Buffer + Polish (~2 hours)
21. Fix broken flows from live testing
22. Add loading states and error messages in frontend
23. Record 2-minute demo video
24. Push to GitHub with clean README

---

## DAY 3.5 — Buffer (Half Day)
Reserved for unexpected bugs and deployment issues. Not for new features.

---

## The Demo Flow (8 steps — memorize this)

1. Open MurphyBot. Log in.
2. Consultation Mode.
3. Type: "I have a bad headache, fever, and my neck feels stiff."
4. Bot: "Is the neck stiffness painful when you try to touch your chin to your chest?"
5. Type: "Yes, very painful."
6. Bot: "Any sensitivity to light or sound?"
7. Type: "Yes, light is unbearable right now."
8. Bot returns:
   - Ranked diagnoses: Bacterial Meningitis (High), Viral Meningitis (Medium), Encephalitis (Low)
   - Red flags + recommended tests
   - Top 5 neurologists/urgent care within 5 miles with ratings
   - 3 PubMed papers on bacterial meningitis
   - FDA drug safety info for suggested antibiotics

This 8-step flow tells the entire product story. Demo this, not the feature list.

---

## Skills This Proves

| Skill | Evidence |
|-------|---------|
| RAG | ChromaDB ingestion, chunking, retrieval |
| Graph RAG | PrimeKG Neo4j traversal, Cypher queries |
| Hybrid retrieval | Graph + vector merge |
| Prompt engineering | 3-state system prompts, structured extraction |
| Agents / tool use | MCP integration, structured outputs |
| Multi-modal | Claude vision for X-rays |
| Observability | LangSmith tracing |
| Auth + RLS | Supabase row-level security |
| API design | FastAPI async |
| Product thinking | Triage state machine, responsible AI |

---

## Security — Do This First

Your Colab file has live OpenAI and Google Maps API keys in plain text.
Rotate BOTH immediately:
- OpenAI: platform.openai.com → API keys → delete and regenerate
- Google: console.cloud.google.com → Credentials → delete and regenerate
Bots scan GitHub for exposed keys within minutes of any public commit.

---

## Total Estimates

Time: 3.5 days
API cost: ~$3-5 total
Infrastructure cost: $0 (all free tiers)

---
Roadmap finalized: 2026-03-01
