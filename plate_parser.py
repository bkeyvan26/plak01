"""Robust Iranian licence-plate grammar parser.

The parser accepts Persian/Arabic/Latin digits, optional ``ایران``/``IRAN``
markers and OCR punctuation.  Incomplete readings are returned but are not
considered confident enough for storage.
"""
from __future__ import annotations
import re
from typing import Dict, Optional

PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
_DIGIT_TRANS = str.maketrans(PERSIAN_DIGITS + ARABIC_DIGITS, "0123456789" * 2)
PERSIAN_LETTERS = "ابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهی"
CATEGORY_BY_LETTER = {
    "ت": "taxi", "ع": "public", "ک": "agricultural", "الف": "government",
    "گ": "temporary", "پ": "police", "ث": "sepah", "ز": "defence_ministry",
    "ش": "army", "ف": "armed_forces_staff", "ژ": "disabled_veteran",
}

def _normalise(text: str) -> str:
    s = str(text or "").strip().translate(_DIGIT_TRANS)
    # Common OCR spellings and mojibake seen in older database records.
    s = s.replace("ي", "ی").replace("ى", "ی").replace("ك", "ک")
    s = re.sub(r"(?i)i[\s._-]*r[\s._-]*a[\s._-]*n", "ایران", s)
    s = s.replace("ط§غŒط±ط§ظ†", "ایران").replace("ط§ظ„ظپ", "الف")
    s = re.sub(r"[\s\-_|/\\()\[\]{}:;,]+", "", s)
    return s

def _display(text: str) -> str:
    s = _normalise(text)
    if "ایران" in s or len(s) < 7:
        return s
    # Canonical display inserts ایران between serial and region for compact OCR.
    return s[:6] + "ایران" + s[6:]

def _category(letter: str, color: Optional[str], blue: bool) -> str:
    if letter in CATEGORY_BY_LETTER:
        return CATEGORY_BY_LETTER[letter]
    c = (color or "").lower()
    if c in {"yellow", "زرد"}: return "public_or_service"
    if c in {"red", "قرمز"}: return "government_or_protocol"
    if c in {"green", "سبز", "khaki", "خاکستری", "blue", "آبی"}: return "military_or_security"
    return "private" if blue else "unknown"

def parse_plate(text: str, plate_color: Optional[str] = None,
                has_blue_strip: bool = True) -> Dict[str, Optional[str]]:
    normalized = _normalise(text)
    result = {"plate": _display(text), "category": "unknown",
              "province_code": None, "serial": None, "letter": None,
              "region_code": None}
    compact = normalized.replace("ایران", "")
    # Standard plate: two digits, one letter (or ?), three digits, two digits.
    m = re.fullmatch(r"([0-9?]{2})(الف|[^\d])([0-9?]{3})([0-9?]{2})", compact)
    if m:
        prefix, letter, serial, region = m.groups()
        result.update(category=_category(letter, plate_color, has_blue_strip),
                      province_code=prefix, serial=serial, letter=letter,
                      region_code=region)
        return result
    if re.fullmatch(r"[0-9]{8}", compact):
        result.update(category="motorcycle", province_code=compact[:3],
                      serial=compact[3:])
    return result

def is_confident_plate(parsed: Dict[str, Optional[str]]) -> bool:
    if parsed.get("category") == "motorcycle":
        return bool(re.fullmatch(r"\d{3}", parsed.get("province_code") or "") and
                    re.fullmatch(r"\d{5}", parsed.get("serial") or ""))
    fields = [parsed.get(k) or "" for k in ("province_code", "serial", "region_code")]
    return bool(re.fullmatch(r"\d{2}", fields[0]) and
                re.fullmatch(r"\d{3}", fields[1]) and
                re.fullmatch(r"\d{2}", fields[2]) and
                      parsed.get("letter") in PERSIAN_LETTERS + "الف?") and "?" not in "".join(fields)
