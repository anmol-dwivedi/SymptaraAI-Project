
import os
import sys
import time
import logging
import pandas as pd
from neo4j import GraphDatabase
from dotenv import load_dotenv

from pathlib import Path
from datetime import datetime

# ── LOGGING SETUP ──────────────────────────────────────────────────────────────
# Create logs directory if it doesn't exist
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
LOG_FILE = LOG_DIR / f"load_primekg_{timestamp}.log"



logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, mode="w")
    ]
)
log = logging.getLogger(__name__)

load_dotenv()

# ── CONFIG ─────────────────────────────────────────────────────────────────────
NEO4J_URI      = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
DATABASE_NAME  = os.getenv("DATABASE_NAME", "neo4j")

KG_CSV = "./primekg_graph_db_csv/kg.csv"

ALLOWED_NODE_TYPES = {"disease", "effect/phenotype", "drug"}
NODE_BATCH_SIZE    = 500
EDGE_BATCH_SIZE    = 1000

# ── RELATION MAP ───────────────────────────────────────────────────────────────
# Maps kg.csv relation values → (src_label, Neo4j_rel_type, dst_label)
RELATION_MAP = {
    # Disease ↔ Phenotype (MOST IMPORTANT — 150k edges, core of triage)
    "disease_phenotype_positive":  ("Disease",   "HAS_PHENOTYPE",        "Phenotype"),
    "disease_phenotype_negative":  ("Disease",   "NOT_HAS_PHENOTYPE",    "Phenotype"),

    # Disease ↔ Drug
    "contraindication":            ("Disease",   "CONTRAINDICATED_WITH", "Drug"),
    "indication":                  ("Disease",   "INDICATED_FOR",        "Drug"),
    "off-label use":               ("Disease",   "OFF_LABEL_USE",        "Drug"),

    # Disease ↔ Disease
    "disease_disease":             ("Disease",   "RELATED_TO",           "Disease"),

    # Drug ↔ Drug
    "drug_drug":                   ("Drug",      "INTERACTS_WITH",       "Drug"),

    # Drug ↔ Phenotype
    "drug_effect":                 ("Drug",      "HAS_SIDE_EFFECT",      "Phenotype"),

    # Phenotype ↔ Phenotype
    "phenotype_phenotype":         ("Phenotype", "RELATED_TO",           "Phenotype"),
}


# ── NEO4J DRIVER ───────────────────────────────────────────────────────────────
class PrimeKGLoader:
    def __init__(self):
        log.info(f"Connecting to Neo4j at {NEO4J_URI}...")
        try:
            self.driver = GraphDatabase.driver(
                NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
            )
            self.driver.verify_connectivity()
            log.info("✅ Neo4j connection successful.")
        except Exception as e:
            log.error(f"❌ FAILED to connect to Neo4j: {e}")
            log.error("Is Neo4j running? Try: sudo systemctl status neo4j")
            sys.exit(1)

    def close(self):
        self.driver.close()

    def run(self, query, parameters=None, database=DATABASE_NAME):
        with self.driver.session(database=database) as session:
            session.run(query, parameters or {})

    def run_read(self, query, database=DATABASE_NAME):
        with self.driver.session(database=database) as session:
            return session.run(query).data()


# ── STEP 0: CLEAR DATABASE ─────────────────────────────────────────────────────
def create_database(loader: PrimeKGLoader):
    log.info("━━━ STEP 0: Database Setup ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    log.info("  Neo4j Community Edition — using default 'neo4j' database.")
    log.info("  Clearing any existing data...")
    try:
        with loader.driver.session(database="neo4j") as session:
            result = session.run("MATCH (n) RETURN count(n) AS count").data()
            existing = result[0]["count"]
            if existing > 0:
                log.info(f"  Found {existing:,} existing nodes — deleting...")
                session.run("MATCH (n) DETACH DELETE n")
                log.info("  Existing data cleared.")
            else:
                log.info("  Database is already empty.")
        log.info("✅ Database 'neo4j' ready (fresh).")
    except Exception as e:
        log.error(f"❌ FAILED at database setup: {e}")
        sys.exit(1)


# ── STEP 1: CREATE INDEXES ─────────────────────────────────────────────────────
def create_indexes(loader: PrimeKGLoader):
    log.info("━━━ STEP 1: Creating Indexes ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    indexes = [
        ("node_id on Disease",   "CREATE INDEX node_id_disease   IF NOT EXISTS FOR (n:Disease)   ON (n.node_id)"),
        ("node_id on Phenotype", "CREATE INDEX node_id_phenotype IF NOT EXISTS FOR (n:Phenotype) ON (n.node_id)"),
        ("node_id on Drug",      "CREATE INDEX node_id_drug      IF NOT EXISTS FOR (n:Drug)      ON (n.node_id)"),
        ("hpo_id on Phenotype",  "CREATE INDEX hpo_id            IF NOT EXISTS FOR (n:Phenotype) ON (n.hpo_id)"),
        ("name on Disease",      "CREATE INDEX disease_name      IF NOT EXISTS FOR (n:Disease)   ON (n.name)"),
        ("name on Phenotype",    "CREATE INDEX phenotype_name    IF NOT EXISTS FOR (n:Phenotype) ON (n.name)"),
        ("name on Drug",         "CREATE INDEX drug_name         IF NOT EXISTS FOR (n:Drug)      ON (n.name)"),
    ]
    for desc, query in indexes:
        try:
            loader.run(query)
            log.info(f"  ✅ Index created: {desc}")
        except Exception as e:
            log.error(f"  ❌ FAILED to create index [{desc}]: {e}")
            sys.exit(1)
    log.info("✅ All indexes created.")


# ── STEP 2: LOAD NODES ─────────────────────────────────────────────────────────
def load_nodes(loader: PrimeKGLoader) -> tuple:
    log.info("━━━ STEP 2: Loading Nodes ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    log.info(f"Reading {KG_CSV}...")
    try:
        df = pd.read_csv(KG_CSV, low_memory=False)
    except FileNotFoundError:
        log.error(f"❌ kg.csv not found at: {KG_CSV}")
        log.error("Check that primekg_graph_db_csv/ is in your root directory.")
        sys.exit(1)

    log.info(f"  Raw rows (edges): {len(df):,}")
    log.info(f"  Columns: {df.columns.tolist()}")

    # Extract unique nodes from BOTH x and y sides of every edge
    x_nodes = df[["x_index", "x_id", "x_type", "x_name", "x_source"]].copy()
    x_nodes.columns = ["node_index", "node_id", "node_type", "node_name", "node_source"]

    y_nodes = df[["y_index", "y_id", "y_type", "y_name", "y_source"]].copy()
    y_nodes.columns = ["node_index", "node_id", "node_type", "node_name", "node_source"]

    all_nodes = pd.concat([x_nodes, y_nodes]).drop_duplicates(subset="node_index")
    log.info(f"  Total unique nodes in kg.csv: {len(all_nodes):,}")
    log.info(f"  Node types found: {sorted(all_nodes['node_type'].unique().tolist())}")

    # Filter to only Disease, Phenotype, Drug
    filtered = all_nodes[all_nodes["node_type"].str.lower().isin(ALLOWED_NODE_TYPES)].copy()
    filtered["node_type_lower"] = filtered["node_type"].str.lower()
    log.info(f"  After filter (Disease + Phenotype + Drug): {len(filtered):,} nodes")

    loaded_ids = set()

    for node_type, label, hpo in [
        ("disease",   "Disease",   False),
        # ("phenotype", "Phenotype", True),
        ("effect/phenotype", "Phenotype", True),
        ("drug",      "Drug",      False),
    ]:
        subset = filtered[filtered["node_type_lower"] == node_type]
        log.info(f"  Loading {len(subset):,} {label} nodes...")
        try:
            _batch_load_nodes(loader, subset, label, loaded_ids, hpo=hpo)
            log.info(f"  ✅ {label} nodes done.")
        except Exception as e:
            log.error(f"  ❌ FAILED loading {label} nodes: {e}")
            sys.exit(1)

    log.info(f"✅ Total nodes loaded: {len(loaded_ids):,}")
    return loaded_ids, df


def _batch_load_nodes(loader, df, label, loaded_ids, hpo=False):
    rows  = df.to_dict("records")
    total = len(rows)

    for i in range(0, total, NODE_BATCH_SIZE):
        batch      = rows[i : i + NODE_BATCH_SIZE]
        props_list = []

        for row in batch:
            node_id = str(row.get("node_index", ""))
            props = {
                "node_id": node_id,
                "name":    str(row.get("node_name", "")),
                "source":  str(row.get("node_source", "")),
            }
            if hpo:
                # node_id column in kg.csv holds the HPO term ID e.g. HP:0001945
                props["hpo_id"] = str(row.get("node_id", ""))
            props_list.append(props)
            loaded_ids.add(node_id)

        if hpo:
            query = f"""
                UNWIND $props AS p
                MERGE (n:{label} {{node_id: p.node_id}})
                SET n.name   = p.name,
                    n.source = p.source,
                    n.hpo_id = p.hpo_id
            """
        else:
            query = f"""
                UNWIND $props AS p
                MERGE (n:{label} {{node_id: p.node_id}})
                SET n.name   = p.name,
                    n.source = p.source
            """

        loader.run(query, {"props": props_list})

        done = min(i + NODE_BATCH_SIZE, total)
        if (i // NODE_BATCH_SIZE) % 10 == 0 or done == total:
            pct = (done / total) * 100
            log.info(f"    {label}: {done:,}/{total:,} ({pct:.0f}%)")


# ── STEP 3: LOAD EDGES ─────────────────────────────────────────────────────────
def load_edges(loader: PrimeKGLoader, loaded_ids: set, df: pd.DataFrame):
    log.info("━━━ STEP 3: Loading Edges ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # Filter to edges where BOTH endpoints are in our subgraph
    df = df.copy()
    df["x_id"] = df["x_index"].astype(str)
    df["y_id"] = df["y_index"].astype(str)
    before = len(df)
    df = df[df["x_id"].isin(loaded_ids) & df["y_id"].isin(loaded_ids)]
    log.info(f"  Edges after filter (both endpoints in subgraph): {len(df):,} / {before:,}")

    # Detect relation column name
    relation_col = "relation" if "relation" in df.columns else "display_relation"
    log.info(f"  Using relation column: '{relation_col}'")
    log.info(f"  Relation types found: {sorted(df[relation_col].unique().tolist())}")

    total_loaded = 0

    for rel_key, (src_label, rel_type, dst_label) in RELATION_MAP.items():
        # Match against both raw and display_relation formats
        mask = df[relation_col].str.lower().str.replace(" ", "_").str.replace("-", "_") == rel_key.replace("-", "_")
    #    mask = df[relation_col].str.lower() == rel_key
        subset = df[mask]

        if subset.empty:
            log.info(f"  ⏭  No edges for: {rel_key}")
            continue

        log.info(f"  Loading {len(subset):,} [{rel_type}] ({src_label} → {dst_label})...")
        try:
            _batch_load_edges(loader, subset, src_label, rel_type, dst_label)
            total_loaded += len(subset)
            log.info(f"  ✅ [{rel_type}] done.")
        except Exception as e:
            log.error(f"  ❌ FAILED [{rel_type}]: {e}")
            sys.exit(1)

    # Catch-all: any relation types not in RELATION_MAP
    normalised = df[relation_col].str.lower().str.replace(" ", "_").str.replace("-", "_")
    mapped_keys = {k.replace("-", "_") for k in RELATION_MAP.keys()}
    remainder = df[~normalised.isin(mapped_keys)]

    if not remainder.empty:
        log.info(f"  Loading {len(remainder):,} unmapped edges as [ASSOCIATED_WITH]...")
        log.info(f"  Unmapped relation types: {remainder[relation_col].unique().tolist()}")
        try:
            _batch_load_edges(loader, remainder, None, "ASSOCIATED_WITH", None, generic=True)
            total_loaded += len(remainder)
            log.info("  ✅ [ASSOCIATED_WITH] done.")
        except Exception as e:
            log.error(f"  ❌ FAILED [ASSOCIATED_WITH]: {e}")
            sys.exit(1)

    log.info(f"✅ Total edges loaded: {total_loaded:,}")


def _batch_load_edges(loader, df, src_label, rel_type, dst_label, generic=False):
    rows  = df[["x_id", "y_id"]].to_dict("records")
    total = len(rows)

    for i in range(0, total, EDGE_BATCH_SIZE):
        batch = rows[i : i + EDGE_BATCH_SIZE]

        if generic:
            query = f"""
                UNWIND $edges AS e
                MATCH (a {{node_id: e.x_id}})
                MATCH (b {{node_id: e.y_id}})
                MERGE (a)-[:{rel_type}]->(b)
            """
        else:
            query = f"""
                UNWIND $edges AS e
                MATCH (a:{src_label} {{node_id: e.x_id}})
                MATCH (b:{dst_label} {{node_id: e.y_id}})
                MERGE (a)-[:{rel_type}]->(b)
            """

        loader.run(query, {"edges": batch})

        done = min(i + EDGE_BATCH_SIZE, total)
        if (i // EDGE_BATCH_SIZE) % 20 == 0 or done == total:
            pct = (done / total) * 100
            log.info(f"    {rel_type}: {done:,}/{total:,} ({pct:.0f}%)")


# ── STEP 4: VERIFY ─────────────────────────────────────────────────────────────
def verify(loader: PrimeKGLoader):
    log.info("━━━ STEP 4: Verification ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    log.info("  Node counts:")
    try:
        counts = loader.run_read("""
            MATCH (n)
            RETURN labels(n)[0] AS label, count(n) AS count
            ORDER BY count DESC
        """)
        for row in counts:
            log.info(f"    {row['label']}: {row['count']:,} nodes")
    except Exception as e:
        log.error(f"  ❌ Node count query failed: {e}")

    log.info("  Edge counts:")
    try:
        edge_counts = loader.run_read("""
            MATCH ()-[r]->()
            RETURN type(r) AS rel, count(r) AS count
            ORDER BY count DESC
        """)
        for row in edge_counts:
            log.info(f"    {row['rel']}: {row['count']:,} edges")
    except Exception as e:
        log.error(f"  ❌ Edge count query failed: {e}")

    log.info("  Triage test — Fever + Neck Stiffness:")
    try:
        results = loader.run_read("""
            MATCH (p:Phenotype)
            WHERE toLower(p.name) IN ["fever", "neck stiffness", "stiff neck"]
            MATCH (p)<-[:HAS_PHENOTYPE]-(d:Disease)
            RETURN d.name AS disease, count(p) AS matched
            ORDER BY matched DESC
            LIMIT 10
        """)
        if results:
            for row in results:
                log.info(f"    {row['disease']} (matched: {row['matched']})")
            log.info("  ✅ Triage query working.")
        else:
            log.warning("  ⚠ Triage query returned 0 results.")
            log.warning("  This may mean disease_phenotype edges use 'display_relation' not 'relation'.")
            log.warning("  Check the relation types logged in Step 3 above.")
    except Exception as e:
        log.error(f"  ❌ Triage query failed: {e}")


# ── MAIN ───────────────────────────────────────────────────────────────────────
def main():
    t_start = time.time()
    log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    log.info("  MurphyBot — PrimeKG Loader Starting")
    log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    loader = PrimeKGLoader()

    try:
        create_database(loader)
        create_indexes(loader)
        loaded_ids, df = load_nodes(loader)
        load_edges(loader, loaded_ids, df)
        verify(loader)
    except SystemExit:
        log.error("❌ Script aborted. Check errors above and in load_primekg.log")
        raise
    finally:
        loader.close()

    elapsed = (time.time() - t_start) / 60
    log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    log.info(f"✅ ALL DONE — Total time: {elapsed:.1f} minutes")
    log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")


if __name__ == "__main__":
    main()