"""
Docling Pipeline: Parse medical PDFs from 'books/' → Markdown in 'docling_output/'
Optimised for large (500+ page) books: text-only, no OCR, no image processing.
Compatible with docling >= 2.x

NOTE: Pylance may show "could not be resolved" warnings for docling imports — 
these are false positives from Pylance's static analysis. The code runs correctly
as long as docling is installed in your Python environment.
"""

import logging
from pathlib import Path

from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

# ── Configuration ──────────────────────────────────────────────────────────────
INPUT_DIR = Path("books")
OUTPUT_DIR = Path("docling_output")

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def build_converter() -> DocumentConverter:
    """Fast text-only converter — skips OCR, images, and table vision models.
    Uses PyPdfiumDocumentBackend, the lightest backend for digital PDFs.
    """
    pipeline_options = PdfPipelineOptions(
        do_ocr=False,                   # PDFs have embedded text — no OCR needed
        do_table_structure=False,       # Skip table ML model (big speed win)
        generate_picture_images=False,  # Don't render or store images
    )

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options,
                backend=PyPdfiumDocumentBackend,  # Fastest backend for text-only extraction
            )
        }
    )
    return converter


def run_pipeline() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    pdf_files = sorted(INPUT_DIR.glob("**/*.pdf"))
    if not pdf_files:
        logger.warning("No PDF files found in '%s'.", INPUT_DIR)
        return

    logger.info("Found %d PDF(s) to process.", len(pdf_files))
    converter = build_converter()

    success, failed = 0, 0

    for pdf_path in pdf_files:
        logger.info("Processing: %s", pdf_path.name)
        try:
            result = converter.convert(str(pdf_path))

            # Export markdown — empty string suppresses any image placeholders
            md_text = result.document.export_to_markdown(image_placeholder="")

            # Preserve sub-directory structure inside books/
            relative = pdf_path.relative_to(INPUT_DIR)
            out_path = OUTPUT_DIR / relative.with_suffix(".md")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(md_text, encoding="utf-8")

            logger.info("  ✓ Saved → %s", out_path)
            success += 1

        except Exception as exc:
            logger.error("  ✗ Failed to process '%s': %s", pdf_path.name, exc)
            failed += 1

    logger.info("Done. %d succeeded, %d failed.", success, failed)


if __name__ == "__main__":
    run_pipeline()