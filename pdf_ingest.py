from __future__ import annotations

import io
import re
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PdfReadError

try:
    import pdfplumber
except Exception:  # pragma: no cover - optional fallback dependency
    pdfplumber = None

try:
    import numpy as np
except Exception:  # pragma: no cover - optional OCR dependency
    np = None

try:
    import pypdfium2 as pdfium
except Exception:  # pragma: no cover - optional OCR dependency
    pdfium = None

try:
    from rapidocr_onnxruntime import RapidOCR
except Exception:  # pragma: no cover - optional OCR dependency
    RapidOCR = None


SECTION_MARKERS = {"instructions", "directions", "method", "preparation", "steps", "notes"}
STOP_MARKERS = {
    "nutrition",
    "servings",
    "yield",
    "prep",
    "cook",
    "time",
    "total",
    "equipment",
}
UNIT_PATTERN = re.compile(
    r"\b(?:cup|cups|tbsp|tablespoon|tablespoons|tsp|teaspoon|teaspoons|oz|ounce|ounces|"
    r"pound|pounds|lb|lbs|g|kg|ml|l|clove|cloves|can|cans|slice|slices|pinch|dash)\b"
)
AMOUNT_PATTERN = re.compile(r"^(?:\d+|\d+\/\d+|\d+\.\d+)\b")


def _ocr_available() -> bool:
    return all(dep is not None for dep in (np, pdfium, RapidOCR))


def _clean_lines(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines()]
    return [line for line in lines if line]


def _find_title(lines: list[str]) -> str:
    for line in lines[:8]:
        if 3 <= len(line) <= 90 and not line.lower().startswith(tuple(SECTION_MARKERS)):
            if re.search(r"[a-zA-Z]", line):
                return line
    return "Imported recipe"


def _normalize_title(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    value = value.replace(" _ ", " - ")
    return value


def _is_low_quality_title(value: str) -> bool:
    text = value.strip()
    if not text or text.lower() == "imported recipe":
        return True
    generic = {
        "read reviews",
        "jump to recipe",
        "print",
        "save",
        "ingredients",
        "directions",
    }
    cleaned = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    if cleaned in generic:
        return True
    if text.isupper() and len(text.split()) <= 4:
        return True
    return False


def _extract_with_pypdf(data: bytes) -> tuple[str, str]:
    try:
        reader = PdfReader(io.BytesIO(data))
    except (PdfReadError, ValueError, TypeError):
        return "", ""
    text_parts = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(text_parts).strip()
    if text:
        return text, "pypdf"

    metadata_title = ""
    metadata = reader.metadata or {}
    title = metadata.get("/Title") if hasattr(metadata, "get") else ""
    if title and isinstance(title, str):
        metadata_title = title.strip()
    return metadata_title, "pypdf-metadata"


def _extract_with_pdfplumber(data: bytes) -> tuple[str, str]:
    if pdfplumber is None:
        return "", ""
    text_parts: list[str] = []
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages:
                text_parts.append(page.extract_text() or "")
    except Exception:
        return "", ""
    text = "\n".join(text_parts).strip()
    return text, "pdfplumber" if text else ""


def _extract_with_ocr(data: bytes, max_pages: int = 3) -> tuple[str, str]:
    if not _ocr_available():
        return "", ""
    text_parts: list[str] = []
    try:
        doc = pdfium.PdfDocument(io.BytesIO(data))
        ocr = RapidOCR()
        page_count = min(len(doc), max_pages)
        for page_index in range(page_count):
            page = doc[page_index]
            pil_image = page.render(scale=2.0).to_pil()
            arr = np.array(pil_image)
            result, _ = ocr(arr)
            if result:
                for line in result:
                    # RapidOCR returns tuples where index 1 is recognized text.
                    if len(line) >= 2 and isinstance(line[1], str):
                        value = line[1].strip()
                        if value:
                            text_parts.append(value)
    except Exception:
        return "", ""
    text = "\n".join(text_parts).strip()
    return text, "rapidocr" if text else ""


def _clean_ingredient_line(line: str) -> str:
    cleaned = re.sub(r"^[\-\u2022\*\s]+", "", line).strip()
    cleaned = re.sub(r"^[^\w\d\(\[]+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def _looks_like_ingredient(line: str) -> bool:
    lowered = line.lower().strip()
    if not lowered:
        return False
    if len(lowered) < 3 or len(lowered) > 120:
        return False
    if any(lowered.startswith(marker) for marker in SECTION_MARKERS | STOP_MARKERS):
        return False
    if UNIT_PATTERN.search(lowered):
        return True
    if AMOUNT_PATTERN.search(lowered):
        return True
    if line.startswith(("-", "*", "•")) and len(lowered.split()) >= 2:
        return True
    return False


def _dedupe_ingredients(items: list[str], title: str) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    title_key = re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
    for item in items:
        key = re.sub(r"[^a-z0-9]+", " ", item.lower()).strip()
        if not key:
            continue
        if key == title_key:
            continue
        if key in seen:
            continue
        # Filter short header-like leftovers.
        if key in {"ingredients", "ingredient", "recipe", "directions", "instructions"}:
            continue
        seen.add(key)
        output.append(item)
    return output


def _extract_ingredients(lines: list[str], title: str) -> list[str]:
    start = None
    for index, line in enumerate(lines):
        if line.lower().startswith("ingredients"):
            start = index + 1
            break

    if start is not None:
        collected: list[str] = []
        for line in lines[start:]:
            lowered = line.lower()
            if any(lowered.startswith(marker) for marker in SECTION_MARKERS | STOP_MARKERS):
                break
            chunks = [chunk.strip() for chunk in re.split(r"[•|;]", line) if chunk.strip()]
            for chunk in chunks:
                cleaned = _clean_ingredient_line(chunk)
                if _looks_like_ingredient(cleaned):
                    collected.append(cleaned)
        collected = _dedupe_ingredients(collected, title)
        if collected:
            return collected

    ingredient_like: list[str] = []
    for line in lines:
        cleaned = _clean_ingredient_line(line)
        if _looks_like_ingredient(cleaned):
            ingredient_like.append(cleaned)

    ingredient_like = _dedupe_ingredients(ingredient_like, title)
    return ingredient_like[:15]


def extract_recipe_from_pdf(uploaded_file: Any) -> dict[str, Any]:
    if uploaded_file is None:
        return {"title": "", "ingredients": [], "raw_text": "", "extraction_method": "none", "warning": ""}

    data = uploaded_file.getvalue() if hasattr(uploaded_file, "getvalue") else uploaded_file.read()
    text, method = _extract_with_pypdf(data)
    metadata_title = text if method == "pypdf-metadata" else ""
    warning = ""

    if len(text.strip()) < 60:
        fallback_text, fallback_method = _extract_with_pdfplumber(data)
        if len(fallback_text.strip()) > len(text.strip()):
            text = fallback_text
            method = fallback_method or method

    if len(text.strip()) < 60:
        ocr_text, ocr_method = _extract_with_ocr(data)
        if len(ocr_text.strip()) > len(text.strip()):
            text = ocr_text
            method = ocr_method or method

    if len(text.strip()) < 20:
        if method == "pypdf-metadata":
            warning = (
                "Only PDF metadata was found (for example, document title), but no recipe text was extractable. "
                "This usually means the PDF is image-only."
            )
        elif not _ocr_available():
            warning = (
                "Could not detect readable text from this PDF. It appears image-based and OCR dependencies are not installed. "
                "Install optional OCR packages or enter recipe details manually below."
            )
        else:
            warning = (
                "Could not detect readable text from this PDF even after OCR. "
                "Please enter recipe details manually below."
            )

    lines = _clean_lines(text)
    title = _find_title(lines)
    if metadata_title and _is_low_quality_title(title):
        title = metadata_title
    title = _normalize_title(title)
    ingredients = _extract_ingredients(lines, title)

    if not ingredients and len(lines) > 0:
        # Keep short candidate lines as a best-effort fallback for manual correction.
        ingredients = [line for line in lines if len(line) <= 90][:10]

    return {
        "title": title,
        "ingredients": ingredients,
        "raw_text": text,
        "extraction_method": method,
        "warning": warning,
    }
