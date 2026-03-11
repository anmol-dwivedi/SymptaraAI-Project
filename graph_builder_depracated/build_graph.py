"""
MurphyBot Knowledge Graph Pipeline
====================================
Entry point. Pass a folder of .md files and builds the full Neo4j
knowledge graph: chunk → NER → LLM extraction → Neo4j ingestion.

Usage:
    python build_graph.py --md_folder ./docling_output
    python build_graph.py --md_folder ./docling_output --skip_constraints
"""

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv
from tqdm import tqdm

from graph_builder.graph_schema import Neo4jSchema
from graph_builder.md_parser import MarkdownChunker
from graph_builder.ner_layer import SciSpacyNER
from graph_builder.llm_extractor import LLMExtractor
from graph_builder.neo4j_writer import Neo4jWriter


load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("murphybot.pipeline")


def run(md_folder: str, skip_constraints: bool = False):
    folder = Path(md_folder)
    if not folder.exists():
        log.error(f"Folder not found: {folder}")
        sys.exit(1)

    md_files = sorted(folder.rglob("*.md"))
    if not md_files:
        log.error(f"No .md files found in {folder}")
        sys.exit(1)

    log.info(f"Found {len(md_files)} markdown file(s)")

    # ── Phase 1: ensure schema constraints exist ──────────────────────────
    log.info("Phase 1 — Applying Neo4j schema constraints...")
    schema = Neo4jSchema()
    if not skip_constraints:
        schema.apply_constraints()
    schema.close()
    log.info("Schema constraints applied.")

    # ── Phase 3: MD parsing ───────────────────────────────────────────────
    log.info("Phase 3 — Parsing markdown files into chunks...")
    chunker = MarkdownChunker()
    all_chunks = []
    for md_path in md_files:
        chunks = chunker.chunk_file(md_path)
        all_chunks.extend(chunks)
        log.info(f"  {md_path.name}: {len(chunks)} chunks")
    log.info(f"Total chunks: {len(all_chunks)}")

    # ── Phase 4: NER + LLM extraction ────────────────────────────────────
    log.info("Phase 4 — NER + LLM structured extraction...")
    ner = SciSpacyNER()
    extractor = LLMExtractor()
    writer = Neo4jWriter()

    success, failed, skipped = 0, 0, 0

    for chunk in tqdm(all_chunks, desc="Extracting", unit="chunk"):
        try:
            # Layer A: deterministic NER
            candidate_entities = ner.extract(chunk["text"])

            if not candidate_entities:
                skipped += 1
                log.debug(f"Skipped (no entities): {chunk['section_title'][:60]}")
                continue

            # Layer B: LLM structured extraction
            extraction = extractor.extract(chunk, candidate_entities)

            if extraction is None:
                failed += 1
                log.warning(f"LLM extraction failed: {chunk['section_title'][:60]}")
                continue

            # ── Phase 5: Neo4j write ──────────────────────────────────────
            writer.write_extraction(extraction, chunk)
            success += 1

        except Exception as e:
            failed += 1
            log.error(f"Error on chunk '{chunk['section_title'][:60]}': {e}")

    writer.close()
    ner.close()

    log.info("=" * 60)
    log.info(f"Pipeline complete.")
    log.info(f"  ✓ Success:  {success}")
    log.info(f"  ✗ Failed:   {failed}")
    log.info(f"  ○ Skipped:  {skipped}")
    log.info(f"  Total:      {len(all_chunks)}")
    log.info("=" * 60)
    log.info("Open http://localhost:7474 to explore the graph.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build MurphyBot knowledge graph")
    parser.add_argument("--md_folder", required=True, help="Path to folder of .md files")
    parser.add_argument("--skip_constraints", action="store_true",
                        help="Skip re-applying Neo4j constraints (if already done)")
    args = parser.parse_args()
    run(args.md_folder, args.skip_constraints)
