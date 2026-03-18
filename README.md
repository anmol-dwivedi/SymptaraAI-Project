# Symptara — AI-Powered Medical Symptom Triage

> **Hybrid RAG & Medical MCP Powered Symptom Triage**
> 
> An intelligent, multi-modal medical consultation system that combines a biomedical knowledge graph, vector-based clinical literature retrieval, and large language models to deliver personalised, evidence-backed differential diagnoses — in real time.

---

## ⚠️ Medical Disclaimer

Symptara is an AI-assisted triage and decision-support tool. It is **not a licensed medical device** and does not replace the advice, diagnosis, or treatment of a qualified healthcare professional. All outputs must be reviewed by a doctor before acting on them. In an emergency, call 911 or your local emergency services immediately.

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [The RAG Pipeline](#the-rag-pipeline)
- [Knowledge Sources](#knowledge-sources)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Environment Variables](#environment-variables)
- [Getting Started](#getting-started)
- [API Reference](#api-reference)
- [Anti-Hallucination Layers](#anti-hallucination-layers)
- [Credits & Attribution](#credits--attribution)

---

## Overview

Symptara conducts a structured, multi-turn medical consultation using a **4-state triage state machine** — `GATHERING → NARROWING → CONCLUSION → POST_CONCLUSION` — where Python controls all state transitions and Claude executes each state. The system integrates:

- **PrimeKG** — a peer-reviewed precision medicine knowledge graph from Harvard Medical School, used to match HPO-mapped symptoms to ranked disease candidates
- **ChromaDB vector search** — over 16 embedded medical reference books for evidence-based clinical context
- **Medical MCP enrichment** — real-time FDA drug data, RxNav drug interaction checking, PubMed literature search, and NLM clinical guidelines
- **Claude Vision** — for analysis of uploaded medical images (X-rays, MRI scans, lab reports, clinical photos)
- **Google Maps Places API** — for post-conclusion specialist and clinic recommendations near the patient

The result is a consultation that feels like talking to a knowledgeable clinical assistant — one that references your actual profile, respects your allergies, avoids conditions inconsistent with your demographics, and surfaces real medical evidence for every recommendation.

---

## Key Features

### 🩺 Structured Multi-Turn Consultation
- 4-state triage machine with clean state transitions controlled entirely by Python
- Each state uses a dedicated, carefully engineered system prompt
- Conversation history capped and sanitised on every turn to prevent role confusion
- Negated symptoms explicitly tracked and excluded from reasoning

### 🧠 Hybrid RAG Pipeline (per turn)
- **Symptom extraction** — Claude parses free text into normalised clinical terms with negations, duration, and severity
- **HPO mapping** — dual pipeline: Claude maps well-known terms, ChromaDB vector search picks up the rest using the Human Phenotype Ontology
- **Knowledge graph query** — Neo4j queries PrimeKG to find diseases matching the patient's HPO ID set, ranked by symptom match ratio
- **Vector retrieval** — multi-query ChromaDB search over 16 medical reference books, deduplicated by chunk ID
- **Context assembly** — all sources merged into a single structured context dict before any Claude call

### 👤 Patient Profile & Anti-Hallucination
- Full medical profile (age, sex, blood type, allergies, chronic conditions, medications, past surgeries) injected as ground truth into every system prompt
- Allergies treated as absolute contraindications
- Sex/age used to exclude physiologically impossible diagnoses
- Negated symptoms explicitly listed to prevent false evidence use

### 📄 Medical File Analysis
- **PDF upload** — text extracted via PyMuPDF, analysed by Claude, persisted to Supabase `session_files`
- **Image upload** — X-rays, MRIs, CT scans, clinical photos, lab report images analysed via Claude Vision
- File analysis persists across all turns in the session — re-injected into every subsequent prompt automatically
- Multiple files per session supported, each displayed with individual markdown-rendered analysis

### 💊 MCP Enrichment (on CONCLUSION)
- **FDA OpenAPI** — drug label data including indications, warnings, contraindications
- **RxNav (NLM)** — drug-drug interaction checking between suggested and current medications, severity-ranked
- **PubMed (NCBI E-utilities)** — top 3 relevant papers for the primary diagnosis
- **NLM Health Topics / MedlinePlus** — clinical guidelines for the top diagnosis
- **Claude** — structured confirmatory test list with urgency levels (STAT / Urgent / Routine)

### 🗺️ Nearby Doctor Finder
- Claude infers the appropriate specialist type from diagnoses
- Google Places API searches by GPS coordinates (preferred) or text location fallback
- Returns rated, linked results with direct Google Maps links

### 📍 Location Access
- Non-skippable location modal on every app launch, page refresh, and new session
- Persistent toggle in the header — grant or revoke at any time
- Reverse geocoding via OpenStreetMap Nominatim (no API key required)
- Location + local time injected into conclusion prompts for timing-aware urgency assessment

### 🎙️ Voice Input
- Browser-native `SpeechRecognition` API for voice-to-text symptom entry
- Input method (`text` / `voice`) tracked and stored per message

### 📋 Medical Report Generation
- Full structured JSON report assembled server-side from all session data
- Client-side HTML template rendered with dark theme + `@media print` override for clean PDF
- One-click "Save as PDF" via browser print dialog
- Report includes: patient profile, clinical summary (Claude-generated), differential diagnoses, confirmatory tests, medications, drug interactions, PubMed references, clinical guidelines, file analyses, and full conversation transcript

### 🔬 LangSmith Tracing
- All Claude calls instrumented with `@traceable` decorators
- Full observability across symptom extraction, HPO mapping, graph queries, triage responses, and report generation

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                          │
│  useConsultation hook → api.ts → FastAPI Backend                 │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│                    FastAPI (Python)                               │
│  /consultation/message  /consultation/upload-file                │
│  /consultation/report   /profile                                 │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│                  Context Assembler                                │
│                                                                  │
│  1. Symptom Extractor (Claude)                                   │
│  2. HPO Mapper (Claude + ChromaDB fallback)                      │
│  3. Graph Service → Neo4j (PrimeKG)                              │
│  4. Vector Service → ChromaDB (16 medical books)                 │
│  5. Memory Service → Supabase                                    │
│  6. File Analyses → Supabase session_files                        │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│                  Triage Controller                                │
│                                                                  │
│  GATHERING → NARROWING → CONCLUSION → POST_CONCLUSION            │
│  (Python controls state, Claude executes each state)             │
└────────────────────────┬────────────────────────────────────────┘
                         │
           ┌─────────────┼──────────────┐
           ▼             ▼              ▼
    MCP Enrichment   Doctor Finder   Report Assembler
    FDA / RxNav      Google Places   Claude Summary
    PubMed / NLM     GPS / Text      Full JSON Report
```

---

## The RAG Pipeline

Every user turn triggers the full pipeline before Claude sees anything:

```
User message
    │
    ├─► Symptom Extractor        → Claude: free text → structured JSON
    │       symptoms, negations, duration, severity
    │
    ├─► Symptom Merger           → deduplicate against accumulated list
    │
    ├─► HPO Mapper               → Claude maps known terms to HP:XXXXXXX IDs
    │       └─► Vector Fallback  → ChromaDB hpo_terms collection (distance < 0.6)
    │
    ├─► Graph Query              → Neo4j: HPO IDs → PrimeKG diseases
    │       MATCH (p:Phenotype)-[:ASSOCIATED_WITH]-(d:Disease)
    │       WHERE p.hpo_id IN $hpo_ids
    │       ranked by match_ratio = matched / total_known_symptoms
    │       + drug lookup per disease
    │
    ├─► Vector Search            → ChromaDB medical_books collection
    │       multi-query: combined + per-symptom, top_k=5, deduped by chunk_id
    │
    ├─► Profile Fetch            → Supabase user_profiles
    │
    └─► File Fetch               → Supabase session_files (all uploads this session)
            │
            └─► Assembled Context → Triage Controller
```

---

## Knowledge Sources

### PrimeKG — Precision Medicine Knowledge Graph
> Harvard Medical School, Zitnik Lab

- **GitHub:** [github.com/mims-harvard/PrimeKG](https://github.com/mims-harvard/PrimeKG)
- **Publication:** Chandak, P., Huang, K., & Zitnik, M. (2023). *Building a knowledge graph to enable precision medicine.* Scientific Data, 10(1), 67. [doi:10.1038/s41597-023-01960-3](https://doi.org/10.1038/s41597-023-01960-3)
- **Harvard Dataverse:** [dataverse.harvard.edu/dataverse/primekg](https://dataverse.harvard.edu/dataverse/primekg)

PrimeKG integrates **20 high-quality biomedical resources** to describe **17,080 diseases** with **4,050,249 relationships** across ten biological scales — protein perturbations, biological pathways, phenotypes, anatomical structures, and the full range of approved and experimental drugs. Symptara uses PrimeKG's disease–phenotype–drug subgraph, stored in Neo4j, to rank differential diagnoses by symptom match ratio.

### Human Phenotype Ontology (HPO)
> The Monarch Initiative

Used to map free-text symptoms to standardised clinical identifiers (e.g. `HP:0001945` for fever), enabling precise graph queries. Embedded in ChromaDB as a vector fallback collection.

### Medical Literature (ChromaDB)
16 medical reference books embedded locally using sentence transformers and stored in ChromaDB's `medical_books` collection. Used to retrieve evidence-based clinical context for triage prompts.

### External APIs
| API | Purpose | Auth |
|-----|---------|------|
| [FDA OpenAPI](https://open.fda.gov/apis/drug/label/) | Drug label data — indications, warnings, contraindications | None required |
| [RxNav (NLM)](https://rxnav.nlm.nih.gov/) | Drug-drug interaction checking via RxCUI codes | None required |
| [NCBI E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25501/) | PubMed literature search | None required |
| [NLM Health Topics](https://wsearch.nlm.nih.gov/ws/query) | Clinical guidelines | None required |
| [Nominatim (OSM)](https://nominatim.org/) | Reverse geocoding | None required |
| [Google Places API](https://developers.google.com/maps/documentation/places/web-service) | Nearby doctor/specialist search | API key required |

---

## Tech Stack

### Backend
| Component | Technology |
|-----------|-----------|
| API Framework | FastAPI (Python) |
| LLM | Anthropic Claude Sonnet (`claude-sonnet-4-20250514`) |
| Knowledge Graph | Neo4j + PrimeKG (Harvard) |
| Vector Store | ChromaDB (persistent, local) |
| Database | Supabase (PostgreSQL) |
| PDF Processing | PyMuPDF (fitz) |
| Observability | LangSmith (`@traceable`) |
| HTTP Client | httpx |
| Settings | pydantic-settings + python-dotenv |

### Frontend
| Component | Technology |
|-----------|-----------|
| Framework | React 18 + TypeScript |
| Build Tool | Vite |
| Styling | Tailwind CSS |
| UI Components | shadcn/ui (Radix UI primitives) |
| Animations | Framer Motion |
| Icons | Lucide React |
| Markdown | react-markdown |
| Routing | React Router v6 |
| Data Fetching | Custom hooks (TanStack Query installed) |
| Voice Input | Web Speech API (`webkitSpeechRecognition`) |
| Testing | Vitest + Playwright |

---

## Project Structure

```
symptara/
├── backend/
│   └── backend/
│       ├── main.py                    # FastAPI app, CORS, router mounts
│       ├── config.py                  # pydantic-settings, .env loading
│       ├── chroma_db/                 # Persistent ChromaDB (HPO + books)
│       ├── routers/
│       │   ├── consultation.py        # /message, /upload-file, /report, /new-session
│       │   └── profile.py             # GET/POST user medical profiles
│       └── services/
│           ├── context_assembler.py   # 7-step hybrid RAG pipeline
│           ├── symptom_extractor.py   # Claude → structured symptom JSON
│           ├── hpo_mapper.py          # Claude + ChromaDB HPO mapping
│           ├── graph_service.py       # Neo4j PrimeKG queries
│           ├── vector_service.py      # ChromaDB book search
│           ├── memory_service.py      # All Supabase CRUD
│           ├── triage_controller.py   # 4-state triage machine
│           ├── file_processor.py      # PDF (PyMuPDF) + Image (Claude Vision)
│           ├── doctor_finder.py       # Specialist inference + Google Places
│           ├── mcp_enrichment.py      # MCP pipeline orchestrator
│           ├── report_assembler.py    # Full session report builder
│           └── mcp/
│               ├── drug_enrichment.py # FDA + RxNav direct API calls
│               ├── guidelines.py      # NLM + Claude confirmatory tests
│               ├── literature.py      # PubMed NCBI E-utilities
│               └── mcp_client.py      # Compatibility stub
│
└── frontend/
    └── src/
        ├── App.tsx                    # React Query, Router, Toasters
        ├── pages/
        │   └── Index.tsx              # Main page, two-panel layout
        ├── components/
        │   ├── ConsultationInput.tsx  # Text + voice + file input bar
        │   ├── FileDropZone.tsx       # Drag-drop file upload area
        │   ├── MessageList.tsx        # Chat bubbles + markdown rendering
        │   ├── ResultsDashboard.tsx   # Left panel — all triage results
        │   ├── ProfileDrawer.tsx      # Identity + Medical Info drawers
        │   ├── UserAccountDropdown.tsx
        │   └── SymptaraLogo.tsx
        ├── hooks/
        │   └── useConsultation.ts     # Central state + all API calls
        ├── lib/
        │   └── api.ts                 # Typed fetch wrapper (localhost:8001)
        └── types/
            └── consultation.ts        # All TypeScript interfaces
```

---

## Environment Variables

Create a `.env` file in the `root` directory:

```env
# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# OpenAI (installed, reserved for future use)
OPENAI_API_KEY=sk-...

# Neo4j (PrimeKG)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_anon_key
SUPABASE_SERVICE_KEY=your_service_role_key

# Google Maps (for doctor finder)
GOOGLE_MAPS_API_KEY=AIza...

# LangSmith (observability)
LANGCHAIN_API_KEY=ls__...
LANGCHAIN_PROJECT=symptara

# Local paths
CHROMA_PATH=./chroma_db
MD_FOLDER=./docling_output
```

### Supabase Schema

The following tables are required:

```sql
-- Sessions
create table sessions (
  session_id    uuid primary key default gen_random_uuid(),
  user_id       text not null,
  status        text default 'active',  -- active | concluded | reset
  final_diagnoses jsonb,
  mcp_enrichment  jsonb,
  location        jsonb,
  timezone        text,
  concluded_at_local text,
  created_at    timestamptz default now()
);

-- Messages
create table messages (
  id            uuid primary key default gen_random_uuid(),
  session_id    uuid references sessions(session_id),
  role          text,  -- user | assistant
  content       text,
  extracted_symptoms jsonb,
  hpo_terms     jsonb,
  input_method  text default 'text',
  created_at    timestamptz default now()
);

-- User Profiles
create table user_profiles (
  user_id              text primary key,
  age                  int,
  sex                  text,
  blood_type           text,
  allergies            jsonb,
  chronic_conditions   jsonb,
  current_medications  jsonb,
  past_surgeries       jsonb,
  updated_at           timestamptz default now()
);

-- Session Files
create table session_files (
  id             uuid primary key default gen_random_uuid(),
  session_id     uuid references sessions(session_id),
  file_type      text,
  storage_path   text,
  claude_analysis text,
  created_at     timestamptz default now()
);
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+ / Bun
- Neo4j 5.x (loaded with PrimeKG data)
- Supabase project (tables as above)

### Backend

```bash
pip install -r requirements.txt
cp .env.example .env      # fill in your keys
uvicorn backend.main:app --reload --port 8001
```

### Frontend

```bash
cd frontend
npm install               # or: bun install
npm run dev               # runs on http://localhost:8080
```

### Loading PrimeKG into Neo4j

1. Download PrimeKG from [Harvard Dataverse](https://dataverse.harvard.edu/dataverse/primekg)
2. Follow the import guide in the [PrimeKG GitHub repository](https://github.com/mims-harvard/PrimeKG)
3. Ensure the following node labels and relationship types exist:
   - Nodes: `Disease`, `Phenotype`, `Drug`
   - Relationships: `ASSOCIATED_WITH`, `INDICATED_FOR`
   - Properties: `hpo_id` on Phenotype, `node_id` on Disease, `name` on all nodes

### Embedding Medical Books (ChromaDB)

Place your medical reference PDFs in the `docling_output/` folder and run the embedding pipeline to populate the `medical_books` ChromaDB collection. The `hpo_terms` collection should be seeded from the HPO ontology OBO file.

---

## API Reference

All endpoints served at `http://localhost:8001`.

### `GET /health`
Returns `{ "status": "ok", "version": "2.0.0" }`

### `POST /consultation/message`
Main triage endpoint. Accepts full consultation state per turn.

```json
{
  "user_id": "uuid",
  "session_id": "uuid | null",
  "message": "string",
  "accumulated_symptoms": ["string"],
  "turn_count": 0,
  "file_analysis": "string | null",
  "lat": 32.7767,
  "lng": -96.7970,
  "location_text": "Dallas, TX, US",
  "input_method": "text | voice",
  "is_post_conclusion": false,
  "timezone": "America/Chicago",
  "local_time": "2026-03-16T17:58:00"
}
```

### `POST /consultation/upload-file`
Multipart form upload. Accepts PDF, JPEG, PNG, WebP (max 10MB). Returns Claude's analysis string.

### `POST /consultation/new-session`
Marks current session as reset, creates and returns a fresh session ID.

### `GET /consultation/report/{session_id}?user_id=uuid`
Returns full structured report JSON for a concluded session.

### `GET /consultation/session/{session_id}`
Returns session record + full message history.

### `POST /profile/`
Upsert user medical profile. Partial updates supported.

### `GET /profile/{user_id}`
Returns user profile, or `null` if not found.

---

## Anti-Hallucination Layers

Symptara uses five layered defences against LLM hallucination:

| Layer | Mechanism |
|-------|-----------|
| **Layer 1** | Patient profile injected as "ground truth" into every system prompt — Claude cannot contradict it |
| **Layer 2** | PrimeKG match ratios presented as factual scores — Claude cannot reorder or contradict graph-derived rankings |
| **Layer 3** | Python controls all state transitions — Claude can never self-advance the triage state |
| **Layer 4** | POST_CONCLUSION strictly scoped — Claude can only explain the existing report, cannot introduce new diagnoses |
| **Layer 5** | Negated symptoms explicitly listed in every prompt — denied symptoms cannot be used as supporting evidence |

---

## Credits & Attribution

### PrimeKG — Precision Medicine Knowledge Graph
> Chandak, P., Huang, K., & Zitnik, M. (2023).  
> *Building a knowledge graph to enable precision medicine.*  
> Scientific Data, 10(1), 67.  
> [https://doi.org/10.1038/s41597-023-01960-3](https://doi.org/10.1038/s41597-023-01960-3)  
> GitHub: [github.com/mims-harvard/PrimeKG](https://github.com/mims-harvard/PrimeKG)  
> Zitnik Lab, Department of Biomedical Informatics, Harvard Medical School

### Human Phenotype Ontology
> Köhler S, et al. (2021). The Human Phenotype Ontology in 2021. *Nucleic Acids Research.*  
> [hpo.jax.org](https://hpo.jax.org)

### Anthropic Claude
> Large language model backbone for symptom extraction, HPO mapping, triage reasoning, vision analysis, and report generation.  
> [anthropic.com](https://www.anthropic.com)

### External Data Sources
- **FDA Open Data** — [open.fda.gov](https://open.fda.gov)
- **RxNav / RxNorm (NLM)** — [rxnav.nlm.nih.gov](https://rxnav.nlm.nih.gov)
- **PubMed (NCBI)** — [pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov)
- **MedlinePlus (NLM)** — [medlineplus.gov](https://medlineplus.gov)
- **OpenStreetMap Nominatim** — [nominatim.org](https://nominatim.org)

---

## License

This project is intended for research and educational demonstration purposes. All third-party data sources (PrimeKG, HPO, FDA, PubMed, NLM) are subject to their respective licenses. Clinical outputs are not validated for medical use and must not be used as a substitute for professional medical advice.

---

<div align="center">
  <strong>Symptara</strong> · Hybrid RAG & Medical MCP Powered Symptom Triage<br/>
  Built with Claude · PrimeKG · Neo4j · ChromaDB · FastAPI · React
</div>