"""
extract-brief-from-doc.py — extract structured chunks from a PRD / BRD /
functional spec for downstream ingestion by the /ingest-prd custom agent.

Usage:
    python scripts/extract-brief-from-doc.py <path-to-doc>

Supported formats:
    .md, .txt, .docx, text-extractable .pdf

Output (stdout):
    JSON with shape:
    {
      "format": "docx" | "pdf" | "markdown" | "text",
      "source_path": "...",
      "total_chars": int,
      "headings_index": [
        {"level": 1, "text": "...", "chunk_id": "c003", "page": null | int}
      ],
      "chunks": [
        {"chunk_id": "c001", "type": "heading" | "paragraph" | "list_item",
         "level": 1 | 2 | 3 | null, "text": "...", "page": null | int}
      ]
    }

Exit codes:
    0 — success
    1 — usage error (bad args, unsupported extension)
    2 — no extractable text (e.g. scanned PDF)
    3 — file read error
    4 — missing optional dependency

Citation contract (consumed by /ingest-prd custom agent):
    - .md / .txt        → heading + chunk_id
    - .docx             → heading + chunk_id (page is null)
    - .pdf              → page + chunk_id (heading best-effort, may be null)

The PDF strategy is deliberately conservative:
    - Chunks by page boundary + paragraph splits within page.
    - Heading detection only on ALL-CAPS lines or numbered-heading
      patterns (``^\\d+(\\.\\d+)*\\s+[A-Z]``). No font-size heuristics —
      pypdf does not give reliable font metadata.
    - Scanned / image-only PDFs exit 2 with a clear hint.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
_NUMBERED_HEADING_RE = re.compile(r"^(\d+(?:\.\d+)*)\s+[A-Z][A-Za-z0-9 ,&/\-:]+$")
_ALL_CAPS_RE = re.compile(r"^[A-Z][A-Z0-9 ,&/\-:]{3,}$")


def _chunk_id(i: int) -> str:
    return f"c{i:03d}"


def _is_probable_heading(line: str) -> tuple[bool, int | None]:
    """Return (is_heading, level_guess_or_None) for a raw line."""
    s = line.strip()
    if not s or len(s) > 120:
        return False, None
    if _NUMBERED_HEADING_RE.match(s):
        depth = s.split(" ", 1)[0].count(".") + 1
        return True, min(depth, 4)
    if _ALL_CAPS_RE.match(s) and len(s.split()) <= 10:
        return True, 2
    return False, None


# --------------------------------------------------------------------------
# Markdown / text
# --------------------------------------------------------------------------
def extract_markdown(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    chunks: list[dict[str, Any]] = []
    headings: list[dict[str, Any]] = []
    idx = 0
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        h = re.match(r"^(#{1,6})\s+(.*)$", line)
        if h:
            level = len(h.group(1))
            txt = h.group(2).strip()
            cid = _chunk_id(idx)
            chunks.append({
                "chunk_id": cid, "type": "heading", "level": level,
                "text": txt, "page": None,
            })
            headings.append({
                "level": level, "text": txt, "chunk_id": cid, "page": None,
            })
            idx += 1
            continue
        # list item?
        li = re.match(r"^\s*[-*+]\s+(.*)$", line)
        if li:
            cid = _chunk_id(idx)
            chunks.append({
                "chunk_id": cid, "type": "list_item", "level": None,
                "text": li.group(1).strip(), "page": None,
            })
            idx += 1
            continue
        cid = _chunk_id(idx)
        chunks.append({
            "chunk_id": cid, "type": "paragraph", "level": None,
            "text": line.strip(), "page": None,
        })
        idx += 1
    return {
        "format": "markdown",
        "source_path": str(path),
        "total_chars": len(text),
        "headings_index": headings,
        "chunks": chunks,
    }


def extract_text(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    chunks: list[dict[str, Any]] = []
    headings: list[dict[str, Any]] = []
    idx = 0
    # Split on blank lines → paragraphs
    for para in re.split(r"\n\s*\n", text):
        p = para.strip()
        if not p:
            continue
        # Treat first line as a heading candidate
        first, *rest = p.splitlines()
        is_h, level = _is_probable_heading(first)
        if is_h:
            cid = _chunk_id(idx)
            chunks.append({
                "chunk_id": cid, "type": "heading", "level": level,
                "text": first.strip(), "page": None,
            })
            headings.append({
                "level": level, "text": first.strip(),
                "chunk_id": cid, "page": None,
            })
            idx += 1
            if rest:
                body = " ".join(r.strip() for r in rest if r.strip())
                if body:
                    cid = _chunk_id(idx)
                    chunks.append({
                        "chunk_id": cid, "type": "paragraph", "level": None,
                        "text": body, "page": None,
                    })
                    idx += 1
        else:
            cid = _chunk_id(idx)
            chunks.append({
                "chunk_id": cid, "type": "paragraph", "level": None,
                "text": " ".join(ln.strip() for ln in p.splitlines()),
                "page": None,
            })
            idx += 1
    return {
        "format": "text",
        "source_path": str(path),
        "total_chars": len(text),
        "headings_index": headings,
        "chunks": chunks,
    }


# --------------------------------------------------------------------------
# DOCX
# --------------------------------------------------------------------------
def extract_docx(path: Path) -> dict[str, Any]:
    try:
        import docx  # type: ignore
        from docx.oxml.ns import qn  # type: ignore
        from docx.table import Table  # type: ignore
        from docx.text.paragraph import Paragraph  # type: ignore
    except ImportError:
        print(json.dumps({
            "error": "missing_dependency",
            "hint": "Install with: pip install python-docx",
        }))
        sys.exit(4)

    doc = docx.Document(str(path))
    chunks: list[dict[str, Any]] = []
    headings: list[dict[str, Any]] = []
    idx = 0
    total_chars = 0

    def _emit_paragraph(para: Any) -> None:
        nonlocal idx, total_chars
        text = (para.text or "").strip()
        if not text:
            return
        total_chars += len(text)
        style = (para.style.name or "") if para.style else ""
        level: int | None = None
        is_heading = False
        if style.startswith("Heading "):
            try:
                level = int(style.split(" ", 1)[1])
                is_heading = True
            except (ValueError, IndexError):
                pass
        elif style == "Title":
            level = 1
            is_heading = True
        if not is_heading:
            h, guessed = _is_probable_heading(text)
            if h:
                is_heading = True
                level = guessed
        cid = _chunk_id(idx)
        if is_heading:
            chunks.append({
                "chunk_id": cid, "type": "heading", "level": level or 2,
                "text": text, "page": None,
            })
            headings.append({
                "level": level or 2, "text": text,
                "chunk_id": cid, "page": None,
            })
        else:
            chunk_type = "paragraph"
            if "List" in style or style.startswith(("List", "Bullet")):
                chunk_type = "list_item"
            chunks.append({
                "chunk_id": cid, "type": chunk_type, "level": None,
                "text": text, "page": None,
            })
        idx += 1

    def _emit_table(table: Any) -> None:
        nonlocal idx, total_chars
        for row in table.rows:
            row_text = " | ".join((c.text or "").strip() for c in row.cells)
            row_text = row_text.strip().strip("|").strip()
            if not row_text:
                continue
            total_chars += len(row_text)
            cid = _chunk_id(idx)
            chunks.append({
                "chunk_id": cid, "type": "paragraph", "level": None,
                "text": f"[table row] {row_text}", "page": None,
            })
            idx += 1

    # Walk body in document order so tables land near their preceding
    # heading. python-docx stores paragraphs / tables as siblings under
    # doc.element.body; dispatch on the XML tag.
    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            _emit_paragraph(Paragraph(child, doc))
        elif child.tag == qn("w:tbl"):
            _emit_table(Table(child, doc))

    if total_chars == 0:
        print(json.dumps({
            "error": "no_extractable_text",
            "hint": "DOCX has no text content (image-only?).",
        }))
        sys.exit(2)

    return {
        "format": "docx",
        "source_path": str(path),
        "total_chars": total_chars,
        "headings_index": headings,
        "chunks": chunks,
    }


# --------------------------------------------------------------------------
# PDF
# --------------------------------------------------------------------------
def extract_pdf(path: Path) -> dict[str, Any]:
    try:
        import pypdf  # type: ignore
    except ImportError:
        print(json.dumps({
            "error": "missing_dependency",
            "hint": "Install with: pip install pypdf",
        }))
        sys.exit(4)

    try:
        reader = pypdf.PdfReader(str(path))
    except Exception as e:  # pypdf raises many different exceptions
        print(json.dumps({
            "error": "pdf_read_failed",
            "hint": f"pypdf could not read the file: {e}",
        }))
        sys.exit(3)

    chunks: list[dict[str, Any]] = []
    headings: list[dict[str, Any]] = []
    idx = 0
    total_chars = 0
    for page_idx, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text() or ""
        except Exception:
            page_text = ""
        page_text = page_text.strip()
        if not page_text:
            continue
        total_chars += len(page_text)
        # Split the page into paragraphs by blank lines, then handle each.
        for para in re.split(r"\n\s*\n", page_text):
            p = para.strip()
            if not p:
                continue
            first, *rest = p.splitlines()
            is_h, level = _is_probable_heading(first)
            if is_h:
                cid = _chunk_id(idx)
                chunks.append({
                    "chunk_id": cid, "type": "heading", "level": level,
                    "text": first.strip(), "page": page_idx,
                })
                headings.append({
                    "level": level, "text": first.strip(),
                    "chunk_id": cid, "page": page_idx,
                })
                idx += 1
                if rest:
                    body = " ".join(r.strip() for r in rest if r.strip())
                    if body:
                        cid = _chunk_id(idx)
                        chunks.append({
                            "chunk_id": cid, "type": "paragraph",
                            "level": None, "text": body, "page": page_idx,
                        })
                        idx += 1
            else:
                cid = _chunk_id(idx)
                chunks.append({
                    "chunk_id": cid, "type": "paragraph", "level": None,
                    "text": " ".join(ln.strip() for ln in p.splitlines()),
                    "page": page_idx,
                })
                idx += 1

    if total_chars == 0:
        print(json.dumps({
            "error": "no_extractable_text",
            "hint": "Scanned / image-only PDF. Export to .docx or run OCR first.",
        }))
        sys.exit(2)

    return {
        "format": "pdf",
        "source_path": str(path),
        "total_chars": total_chars,
        "headings_index": headings,
        "chunks": chunks,
    }


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Extract structured chunks from a PRD / BRD / spec for /ingest-prd.",
    )
    ap.add_argument("path", help="Path to .md, .txt, .docx, or .pdf")
    args = ap.parse_args(argv)

    src = Path(args.path).expanduser()
    if not src.exists():
        print(json.dumps({"error": "not_found", "hint": f"No file at {src}"}))
        return 3
    if not src.is_file():
        print(json.dumps({"error": "not_a_file", "hint": str(src)}))
        return 3

    ext = src.suffix.lower()
    try:
        if ext in (".md", ".markdown"):
            result = extract_markdown(src)
        elif ext == ".txt":
            result = extract_text(src)
        elif ext == ".docx":
            result = extract_docx(src)
        elif ext == ".pdf":
            result = extract_pdf(src)
        else:
            print(json.dumps({
                "error": "unsupported_format",
                "hint": "Supported: .md, .txt, .docx, .pdf",
            }))
            return 1
    except SystemExit:
        raise
    except Exception as e:
        print(json.dumps({
            "error": "extract_failed",
            "hint": f"{type(e).__name__}: {e}",
        }))
        return 3

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
