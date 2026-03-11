import base64
import fitz  # PyMuPDF
import anthropic
from langsmith import traceable
from config import settings

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
SUPPORTED_PDF_TYPE    = "application/pdf"
MAX_PDF_CHARS         = 8000   # cap to avoid bloating context window
MAX_PDF_PAGES         = 20     # ignore very long documents beyond this


# ── PDF Processing ────────────────────────────────────────────────────────────
def process_pdf(file_bytes: bytes) -> dict:
    """
    Extract text from a user-uploaded PDF using PyMuPDF.

    Handles:
      - Lab reports
      - Discharge summaries
      - Prescription printouts
      - Medical history documents

    Returns:
        {
            "success": bool,
            "text": str,        ← extracted text, injected into context
            "page_count": int,
            "error": str | None
        }
    """
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        page_count = len(doc)

        pages_to_read = min(page_count, MAX_PDF_PAGES)
        extracted_pages = []

        for i in range(pages_to_read):
            page = doc[i]
            text = page.get_text().strip()
            if text:
                extracted_pages.append(f"[Page {i+1}]\n{text}")

        doc.close()

        if not extracted_pages:
            return {
                "success": False,
                "text": "",
                "page_count": page_count,
                "error": "This appears to be a scanned PDF with no text layer. "
                         "Please take a photo of the document instead."
            }

        full_text = "\n\n".join(extracted_pages)

        # Truncate if too long
        if len(full_text) > MAX_PDF_CHARS:
            full_text = full_text[:MAX_PDF_CHARS] + \
                        "\n\n[Document truncated — showing first portion only]"

        return {
            "success": True,
            "text": full_text,
            "page_count": page_count,
            "error": None
        }

    except Exception as e:
        return {
            "success": False,
            "text": "",
            "page_count": 0,
            "error": f"Failed to read PDF: {str(e)}"
        }


# ── Image Processing ──────────────────────────────────────────────────────────
VISION_PROMPT = """Analyze this medical image carefully.

Step 1 — Identify the image type:
- Phone photo (rash, wound, swelling, skin condition, eye, etc.)
- X-ray (chest, limb, spine, etc.)
- MRI or CT scan
- Lab result or printed report
- Other medical document

Step 2 — Describe all clinically relevant findings:
- Be specific and precise
- Use clinical terminology where appropriate
- Note location, size, color, pattern where visible
- For imaging: note any obvious abnormalities, opacities, fractures, masses

Step 3 — Note limitations:
- What cannot be determined from this image alone
- Whether the image quality affects your assessment

Important: This analysis supports a doctor's assessment, not replaces it.
Do not provide a diagnosis — only describe what is visible."""


@traceable(name="vision-file-analysis")
def process_image(file_bytes: bytes, media_type: str) -> dict:
    """
    Analyze a medical image using Claude Vision.

    Handles all image types with a single universal prompt:
      - Phone photos (rash, wound, swelling)
      - X-rays
      - MRI / CT scans
      - Photos of printed lab results

    Claude self-identifies the image type and adjusts its description.

    Returns:
        {
            "success": bool,
            "analysis": str,    ← Claude's description, injected into context
            "image_type": str,  ← what Claude identified it as
            "error": str | None
        }
    """
    if media_type not in SUPPORTED_IMAGE_TYPES:
        return {
            "success": False,
            "analysis": "",
            "image_type": "unknown",
            "error": f"Unsupported image type: {media_type}. "
                     f"Please upload JPEG, PNG, or WebP."
        }

    try:
        image_data = base64.standard_b64encode(file_bytes).decode("utf-8")

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data
                            }
                        },
                        {
                            "type": "text",
                            "text": VISION_PROMPT
                        }
                    ]
                }
            ]
        )

        analysis = response.content[0].text.strip()

        # Extract image type from Claude's response (first line usually says it)
        image_type = "medical image"
        first_line = analysis.split("\n")[0].lower()
        if "x-ray" in first_line or "xray" in first_line:
            image_type = "X-ray"
        elif "mri" in first_line:
            image_type = "MRI scan"
        elif "ct" in first_line:
            image_type = "CT scan"
        elif "photo" in first_line or "rash" in first_line or "wound" in first_line:
            image_type = "clinical photo"
        elif "lab" in first_line or "report" in first_line:
            image_type = "lab report photo"

        return {
            "success": True,
            "analysis": analysis,
            "image_type": image_type,
            "error": None
        }

    except Exception as e:
        return {
            "success": False,
            "analysis": "",
            "image_type": "unknown",
            "error": f"Failed to analyze image: {str(e)}"
        }


# ── Unified entry point ───────────────────────────────────────────────────────
def process_file(file_bytes: bytes, media_type: str, filename: str = "") -> dict:
    """
    Unified file processor. Routes to PDF or image handler based on media_type.

    Returns a standard dict with:
        {
            "success":    bool,
            "file_type":  "pdf" | "image",
            "analysis":   str,   ← text to inject into context_assembler
            "error":      str | None
        }
    """
    if media_type == SUPPORTED_PDF_TYPE:
        result = process_pdf(file_bytes)
        return {
            "success":   result["success"],
            "file_type": "pdf",
            "analysis":  f"Uploaded PDF ({result['page_count']} pages):\n\n{result['text']}"
                         if result["success"] else "",
            "error":     result["error"]
        }

    elif media_type in SUPPORTED_IMAGE_TYPES:
        result = process_image(file_bytes, media_type)
        return {
            "success":   result["success"],
            "file_type": "image",
            "analysis":  f"Uploaded {result['image_type']} analysis:\n\n{result['analysis']}"
                         if result["success"] else "",
            "error":     result["error"]
        }

    else:
        # Try to infer from filename extension as fallback
        ext = filename.lower().split(".")[-1] if "." in filename else ""
        if ext == "pdf":
            return process_file(file_bytes, SUPPORTED_PDF_TYPE, filename)
        elif ext in ("jpg", "jpeg"):
            return process_file(file_bytes, "image/jpeg", filename)
        elif ext == "png":
            return process_file(file_bytes, "image/png", filename)

        return {
            "success":   False,
            "file_type": "unknown",
            "analysis":  "",
            "error":     f"Unsupported file type: {media_type}. "
                         f"Supported: PDF, JPEG, PNG, WebP."
        }