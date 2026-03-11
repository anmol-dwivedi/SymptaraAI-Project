"""
md_parser.py
============
Phase 3 — Parses markdown files into structured chunks.
Splits on H2 headings, preserves H1 as chapter context.
Each chunk carries full metadata for evidence tracing.
"""

import hashlib
import logging
import re
from pathlib import Path
from typing import List, Dict

import tiktoken

log = logging.getLogger("murphybot.parser")

# Token budget per chunk. LLM extraction prompt adds ~400 tokens overhead.
MAX_CHUNK_TOKENS = int(__import__("os").getenv("CHUNK_SIZE_TOKENS", "1200"))
TOKENIZER = tiktoken.get_encoding("cl100k_base")


def _count_tokens(text: str) -> int:
    return len(TOKENIZER.encode(text))


def _chunk_id(source_book: str, section_title: str, text: str) -> str:
    raw = f"{source_book}|{section_title}|{text[:200]}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class MarkdownChunker:
    """
    Splits an MD file into chunks, one per H2 (##) section.
    Tracks the H1 chapter heading for each section as metadata.
    If a section exceeds MAX_CHUNK_TOKENS, it is further split at H3 (###).
    """

    def chunk_file(self, md_path: Path) -> List[Dict]:
        text = md_path.read_text(encoding="utf-8")
        source_book = md_path.name
        chunks = []

        # Split into lines for heading detection
        lines = text.splitlines()

        current_h1 = "Unknown Chapter"
        current_h2 = None
        current_lines: List[str] = []

        def flush(h1, h2, body_lines):
            body = "\n".join(body_lines).strip()
            if not body or len(body) < 100:
                return  # Too short to be useful
            chunks.extend(_make_chunks(source_book, h1, h2 or h1, body))

        for line in lines:
            if line.startswith("# ") and not line.startswith("## "):
                # H1 — new chapter
                if current_h2 and current_lines:
                    flush(current_h1, current_h2, current_lines)
                current_h1 = line.lstrip("# ").strip()
                current_h2 = None
                current_lines = []

            elif line.startswith("## "):
                # H2 — new section: flush previous
                if current_lines:
                    flush(current_h1, current_h2, current_lines)
                current_h2 = line.lstrip("# ").strip()
                current_lines = []

            else:
                current_lines.append(line)

        # Flush final section
        if current_lines:
            flush(current_h1, current_h2, current_lines)

        return chunks


def _make_chunks(
    source_book: str,
    chapter: str,
    section_title: str,
    body: str,
) -> List[Dict]:
    """
    If body fits in MAX_CHUNK_TOKENS, return as single chunk.
    Otherwise split at H3 (###) boundaries.
    """
    if _count_tokens(body) <= MAX_CHUNK_TOKENS:
        return [_build_chunk(source_book, chapter, section_title, body)]

    # Try splitting at H3
    h3_pattern = re.compile(r"^### .+", re.MULTILINE)
    parts = h3_pattern.split(body)
    headers = [""] + h3_pattern.findall(body)

    chunks = []
    for header, part in zip(headers, parts):
        sub_title = f"{section_title} — {header.lstrip('# ').strip()}" if header else section_title
        sub_body  = (header + "\n" + part).strip()
        if not sub_body or len(sub_body) < 80:
            continue

        # If still too long, hard-split by sentence groups
        if _count_tokens(sub_body) > MAX_CHUNK_TOKENS:
            for hard_chunk in _hard_split(sub_body, MAX_CHUNK_TOKENS):
                chunks.append(_build_chunk(source_book, chapter, sub_title, hard_chunk))
        else:
            chunks.append(_build_chunk(source_book, chapter, sub_title, sub_body))

    return chunks if chunks else [_build_chunk(source_book, chapter, section_title, body[:3000])]


def _hard_split(text: str, max_tokens: int) -> List[str]:
    """Split text into token-bounded segments at sentence boundaries."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    segments, current, current_tokens = [], [], 0
    for sent in sentences:
        t = _count_tokens(sent)
        if current_tokens + t > max_tokens and current:
            segments.append(" ".join(current))
            current, current_tokens = [sent], t
        else:
            current.append(sent)
            current_tokens += t
    if current:
        segments.append(" ".join(current))
    return segments


def _build_chunk(
    source_book: str,
    chapter: str,
    section_title: str,
    text: str,
) -> Dict:
    return {
        "chunk_id":      _chunk_id(source_book, section_title, text),
        "source_book":   source_book,
        "chapter":       chapter,
        "section_title": section_title,
        "text":          text,
        "token_count":   _count_tokens(text),
    }
