# MurphyBot — Environment Setup Guide

## Part 1: Neo4j on Ubuntu

### Step 1 — Install Java 21 (required by Neo4j 5.x)

```bash
sudo apt update
sudo apt install -y openjdk-21-jdk

# Confirm Java version
java -version
# Should print: openjdk version "21.x.x"

# If you have multiple Java versions, set 21 as default
sudo update-java-alternatives --list
# Pick the java-1.21.0-openjdk-amd64 entry from the list, then:
sudo update-java-alternatives --jre --set java-1.21.0-openjdk-amd64
```

---

### Step 2 — Add the Neo4j apt repository

```bash
# Install transport helpers
sudo apt install -y apt-transport-https ca-certificates curl gnupg

# Add Neo4j GPG key (modern method — no deprecated apt-key)
wget -O - https://debian.neo4j.com/neotechnology.gpg.key \
  | sudo gpg --dearmor -o /etc/apt/keyrings/neotechnology.gpg

# Add Neo4j 5 repository (pinned to major version 5 — won't auto-jump to 6)
echo 'deb [signed-by=/etc/apt/keyrings/neotechnology.gpg] https://debian.neo4j.com stable 5' \
  | sudo tee /etc/apt/sources.list.d/neo4j.list

sudo apt update
```

---

### Step 3 — Install Neo4j Community Edition

```bash
sudo apt install -y neo4j

# Confirm it installed
neo4j --version
```

---

### Step 4 — Enable and start the service

```bash
sudo systemctl enable neo4j        # start at boot
sudo systemctl start neo4j
sudo systemctl status neo4j        # should show "active (running)"
```

---

### Step 5 — Set the initial password

Neo4j ships with username `neo4j` and password `neo4j`.
You must change it on first login via cypher-shell:

```bash
cypher-shell -u neo4j -p neo4j
```

When prompted to change the password, set something strong, e.g. `MurphyBot2025!`

Then inside the cypher-shell, verify connection:
```cypher
RETURN "Neo4j is running" AS status;
:exit
```

Alternatively, open your browser at `http://localhost:7474` — the Neo4j Browser UI.
First login: username `neo4j`, password `neo4j`, then it will ask you to change it.

---

### Step 6 — Neo4j configuration (optional but recommended)

```bash
sudo nano /etc/neo4j/neo4j.conf
```

Useful settings to check / uncomment:

```
# Allow connections from anywhere (if accessing from another machine)
server.default_listen_address=0.0.0.0

# Bolt port (Python driver connects here)
server.bolt.listen_address=0.0.0.0:7687

# Memory tuning for large medical corpus ingestion
server.memory.heap.initial_size=1g
server.memory.heap.max_size=4g
server.memory.pagecache.size=2g
```

After editing:
```bash
sudo systemctl restart neo4j
```

---

### Step 7 — Verify Python can connect

```bash
pip install neo4j
python3 -c "
from neo4j import GraphDatabase
driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'MurphyBot2025!'))
with driver.session() as s:
    result = s.run('RETURN 1 AS n')
    print('Connected:', result.single()['n'])
driver.close()
"
# Should print: Connected: 1
```

---

## Part 2: Conda Environment Setup

### Step 1 — Create the environment

```bash
conda create -n murphybot python=3.10 -y
conda activate murphybot
```

> **Why Python 3.10?** scispacy 0.5.x/0.6.x is fully tested on 3.9–3.10.
> Python 3.11+ has occasional nmslib build issues.

---

### Step 2 — Install core packages

```bash
# Core NLP + graph + LLM stack
pip install \
  scispacy==0.5.4 \
  spacy \
  langchain \
  langchain-openai \
  langchain-community \
  langchain-text-splitters \
  neo4j \
  openai \
  python-dotenv \
  pydantic \
  tqdm \
  tiktoken \
  chromadb \
  tenacity
```

---

### Step 3 — Install SciSpacy models

These are installed from direct S3 URLs — they are not on PyPI.

```bash
# BC5CDR NER model — Disease + Chemical/Drug NER (PRIMARY model for MurphyBot)
pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_ner_bc5cdr_md-0.5.4.tar.gz

# General biomedical pipeline — used by UMLS EntityLinker
pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_core_sci_lg-0.5.4.tar.gz
```

The UMLS knowledge base (~1GB) downloads automatically on first use of the EntityLinker.
It is cached at `~/.scispacy/` after the first download.

---

### Step 4 — Verify scispacy install

```bash
python3 -c "
import spacy
import scispacy
from scispacy.abbreviation import AbbreviationDetector
from scispacy.linking import EntityLinker

nlp = spacy.load('en_ner_bc5cdr_md')
nlp.add_pipe('abbreviation_detector')
# Note: EntityLinker will download ~1GB UMLS KB on first call — be patient
print('SciSpacy loaded OK. Models ready.')
"
```

---

### Step 5 — Set environment variables

Create a `.env` file in your project root:

```bash
cat > .env << 'EOF'
# OpenAI
OPENAI_API_KEY=sk-...your-key-here...

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=MurphyBot2025!

# Pipeline settings
MD_FOLDER=./docling_output
CHUNK_SIZE_TOKENS=1200
LLM_EXTRACTION_MODEL=gpt-4o-mini
LLM_REASONING_MODEL=gpt-4o
UMLS_CONFIDENCE_THRESHOLD=0.85
EOF
```

---

### Full package list summary

| Package | Purpose |
|---------|---------|
| `scispacy==0.5.4` | Biomedical NLP framework |
| `en_ner_bc5cdr_md` | Disease + Drug NER (via URL) |
| `en_core_sci_lg` | UMLS entity linker base (via URL) |
| `spacy` | NLP base |
| `langchain` | MD parsing, text splitting |
| `langchain-openai` | GPT-4o/mini integration |
| `langchain-community` | Neo4j integration |
| `neo4j` | Neo4j Python driver |
| `openai` | Direct OpenAI API calls |
| `chromadb` | Vector store (Phase 9) |
| `python-dotenv` | Environment variable loading |
| `pydantic` | JSON schema validation |
| `tqdm` | Progress bars |
| `tiktoken` | Token counting |
| `tenacity` | API retry logic |
