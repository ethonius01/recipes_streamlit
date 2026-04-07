from __future__ import annotations

import io
import re
import shutil
from functools import lru_cache
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PdfReadError


IMPORT_ERRORS: dict[str, str] = {}

try:
    import pdfplumber
except Exception as exc:  # pragma: no cover - optional fallback dependency
    pdfplumber = None
    IMPORT_ERRORS["pdfplumber"] = str(exc)

try:
    import pypdfium2 as pdfium
except Exception as exc:  # pragma: no cover - optional OCR dependency
    pdfium = None
    IMPORT_ERRORS["pypdfium2"] = str(exc)

try:
    import pytesseract
except Exception as exc:  # pragma: no cover - optional OCR dependency
    pytesseract = None
    IMPORT_ERRORS["pytesseract"] = str(exc)


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
    return all(dep is not None for dep in (pdfium, pytesseract)) and shutil.which("tesseract") is not None


def parser_capabilities() -> dict[str, Any]:
    return {
        "pdfplumber": pdfplumber is not None,
        "pypdfium2": pdfium is not None,
        "pytesseract": pytesseract is not None,
        "tesseract_binary": shutil.which("tesseract") is not None,
        "ocr_available": _ocr_available(),
        "import_errors": dict(IMPORT_ERRORS),
    }


@lru_cache(maxsize=1)
def _get_ocr_engine() -> Any:
    if not _ocr_available():
        return None
    return pytesseract


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


def _extract_with_ocr(data: bytes, max_pages: int = 2) -> tuple[str, str]:
    engine = _get_ocr_engine()
    if engine is None:
        return "", ""
    text_parts: list[str] = []
    try:
        doc = pdfium.PdfDocument(io.BytesIO(data))
        page_count = min(len(doc), max_pages)
        for page_index in range(page_count):
            page = doc[page_index]
            pil_image = page.render(scale=2.0).to_pil()
            ocr_text = engine.image_to_string(pil_image, config="--psm 6")
            if ocr_text:
                text_parts.append(ocr_text)
    except Exception:
        return "", ""
    text = "\n".join(text_parts).strip()
    return text, "pytesseract" if text else ""


def _text_quality_score(text: str, method: str) -> float:
    value = text.strip()
    if not value:
        return -999.0
    lines = _clean_lines(value)
    ingredient_hits = sum(1 for line in lines if _looks_like_ingredient(_clean_ingredient_line(line)))
    score = (len(lines) * 0.8) + (ingredient_hits * 4.0) + min(len(value) / 120.0, 8.0)
    if method == "pypdf-metadata":
        score -= 6.0
    if method == "pytesseract":
        score += 1.0
    return score


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
    diagnostics: list[str] = []
    candidates: list[tuple[str, str]] = []
    if text.strip():
        candidates.append((text, method))

    if len(text.strip()) < 60:
        fallback_text, fallback_method = _extract_with_pdfplumber(data)
        if fallback_text.strip():
            candidates.append((fallback_text, fallback_method or "pdfplumber"))
        if len(fallback_text.strip()) > len(text.strip()):
            text = fallback_text
            method = fallback_method or method
            diagnostics.append("pdfplumber fallback used")
        elif not fallback_text.strip():
            diagnostics.append("pdfplumber returned no text")

    if len(text.strip()) < 60:
        ocr_text, ocr_method = _extract_with_ocr(data)
        if ocr_text.strip():
            candidates.append((ocr_text, ocr_method or "pytesseract"))
        if len(ocr_text.strip()) > len(text.strip()):
            text = ocr_text
            method = ocr_method or method
            diagnostics.append("OCR fallback used")
        elif _ocr_available():
            diagnostics.append("OCR returned no text")
        else:
            diagnostics.append("OCR unavailable in runtime")

    if candidates:
        best_text, best_method = max(candidates, key=lambda item: _text_quality_score(item[0], item[1]))
        if (best_text, best_method) != (text, method):
            text = best_text
            method = best_method
            diagnostics.append(f"selected best extraction: {best_method}")

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

    if not _ocr_available():
        capabilities = parser_capabilities()
        missing = [key for key, ok in capabilities.items() if key in {"pypdfium2", "pytesseract", "tesseract_binary"} and ok is False]
        if missing:
            diagnostics.append("missing OCR deps: " + ", ".join(sorted(missing)))

    lines = _clean_lines(text)
    title = _find_title(lines)
    if metadata_title and _is_low_quality_title(title):
        title = metadata_title
    title = _normalize_title(title)
    ingredients = _extract_ingredients(lines, title)

    if not ingredients and len(lines) > 0:
        # Keep short candidate lines as a best-effort fallback for manual correction.
        ingredients = [line for line in lines if len(line) <= 90][:10]

    if diagnostics and method:
        warning = warning or f"Extraction path: {method}. {'; '.join(diagnostics)}"

    return {
        "title": title,
        "ingredients": ingredients,
        "raw_text": text,
        "extraction_method": method,
        "warning": warning,
        "diagnostics": diagnostics,
    }
