from __future__ import annotations

"""Resume ingestion: bytes in, text + structured profile out.

Owns the whole extraction policy — Reducto first (layout-aware, handles
multi-column resumes and tables), local PDF libraries as the fallback — so the
route handlers never have to know the order or repeat the "parse it if we don't
have it" rule.
"""

import io
from typing import Any, Callable, Dict, List, Optional, Tuple

from .resume_parser import parse_resume_structured


def _via_pymupdf(data: bytes) -> str:
    import fitz  # type: ignore
    doc = fitz.open(stream=data, filetype="pdf")
    try:
        return "\n".join(page.get_text("text") for page in doc)
    finally:
        doc.close()


def _via_pypdf(data: bytes) -> str:
    import pypdf  # type: ignore
    reader = pypdf.PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() for page in reader.pages)


def _via_pdfplumber(data: bytes) -> str:
    import pdfplumber  # type: ignore
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


# Tried in order; the first library that is installed wins.
_LOCAL_EXTRACTORS: Tuple[Tuple[str, Callable[[bytes], str]], ...] = (
    ("PyMuPDF", _via_pymupdf),
    ("pypdf", _via_pypdf),
    ("pdfplumber", _via_pdfplumber),
)


def extract_pdf_text_locally(data: bytes) -> str:
    """Extract PDF text with whichever library is installed."""
    tried: List[str] = []
    for name, extract in _LOCAL_EXTRACTORS:
        try:
            text = extract(data)
        except ImportError:
            tried.append(name)
            continue
        print(f"📄 PDF parsed with {name}")
        return text

    raise RuntimeError(
        f"No PDF parsing library available (tried {', '.join(tried)}). "
        "Install PyMuPDF, pypdf, or pdfplumber."
    )


def structured_profile(text: str) -> Optional[Dict[str, Any]]:
    """Parse resume text into sections, returning None if the parser blows up."""
    try:
        return parse_resume_structured(text)
    except Exception as e:
        print(f"⚠️ Structured resume parsing failed: {e}")
        return None


async def parse_resume(data: bytes, filename: str) -> Dict[str, Any]:
    """Reducto → local. Returns {text, structured, parser}.

    Raises RuntimeError when no text could be recovered by any engine.
    """
    text = ""
    structured: Optional[Dict[str, Any]] = None
    parser = "local"

    try:
        from .reducto_parser import parse_resume_with_reducto
        result = await parse_resume_with_reducto(data, filename or "resume.pdf")
        if result and result.get("text", "").strip():
            text = result["text"]
            structured = result.get("structured")
            parser = "reducto"
    except Exception as e:
        print(f"⚠️ Reducto parsing failed, falling back to local: {e}")

    if not text.strip():
        text = extract_pdf_text_locally(data)

    if not text.strip():
        raise RuntimeError("No text could be extracted from the PDF")

    if structured is None:
        structured = structured_profile(text)

    return {"text": text, "structured": structured, "parser": parser}
