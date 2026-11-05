"""Sri Lankan Tamil / English product alias matching and unit helpers."""

from __future__ import annotations

from decimal import Decimal
from typing import Dict, List, Optional, Tuple

# Canonical synonym clusters covering Sri Lankan & Indian Tamil shop terms + Tanglish
PRODUCT_SYNONYM_GROUPS: List[List[str]] = [
    ["rice", "arisi", "அரிசி", "பச்சரிசி", "புழுங்கல் அரிசி", "சம்பா"],
    ["sugar", "seeni", "sakkarai", "sarkkarai", "சீனி", "சர்க்கரை", "சக்கரை"],
    ["milk", "paal", "பால்", "பசும்பால்"],
    ["soap", "soppu", "savakkaram", "சோப்பு", "சோப்", "சவர்க்காரம்"],
    ["tea", "theilai", "theyilai", "tea dust", "தேயிலை", "தேநீர் தூள்", "டீ தூள்", "டீ"],
    ["flour", "wheat flour", "maa", "maavu", "மா", "மாவு", "கோதுமை மா"],
    ["dhal", "lentils", "paruppu", "பருப்பு", "மைசூர் பருப்பு"],
    ["oil", "coconut oil", "ennai", "எண்ணெய்", "தேங்காய் எண்ணெய்"],
    ["salt", "uppu", "உப்பு"],
    ["bread", "paan", "rotti", "பாண்", "ரொட்டி"],
    ["egg", "eggs", "muttai", "முட்டை"],
    ["biscuit", "biscuits", "பிஸ்கட்"],
]

TAMIL_UNIT_LABELS: Dict[str, str] = {
    "Pieces": "துண்டுகள்",
    "Kilograms": "கிலோ",
    "Grams": "கிராம்",
    "Litres": "லிட்டர்",
    "Bottles": "போத்தல்",
    "Packets": "பாக்கெட்",
    "Boxes": "பெட்டி",
    "Bags": "மூட்டை",
}

SHORT_UNIT_LABELS: Dict[str, str] = {
    "Pieces": "pcs",
    "Kilograms": "kg",
    "Grams": "g",
    "Litres": "litre",
    "Bottles": "bottles",
    "Packets": "packets",
    "Boxes": "boxes",
    "Bags": "bags",
}

UNIT_CANONICAL_MAP: Dict[str, str] = {
    "piece": "Pieces",
    "pieces": "Pieces",
    "pc": "Pieces",
    "pcs": "Pieces",
    "துண்டு": "Pieces",
    "துண்டுகள்": "Pieces",
    "க்கட்டி": "Pieces",
    "கட்டி": "Pieces",
    "kg": "Kilograms",
    "kgs": "Kilograms",
    "kilo": "Kilograms",
    "kilos": "Kilograms",
    "kilogram": "Kilograms",
    "kilograms": "Kilograms",
    "கிலோ": "Kilograms",
    "கிலோகிராம்": "Kilograms",
    "g": "Grams",
    "gm": "Grams",
    "gram": "Grams",
    "grams": "Grams",
    "கிராம்": "Grams",
    "l": "Litres",
    "ltr": "Litres",
    "liter": "Litres",
    "liters": "Litres",
    "litre": "Litres",
    "litres": "Litres",
    "லிட்டர்": "Litres",
    "லீற்றர்": "Litres",
    "ml": "Millilitres",
    "மில்லி": "Millilitres",
    "bottle": "Bottles",
    "bottles": "Bottles",
    "போத்தல்": "Bottles",
    "பாட்டில்": "Bottles",
    "packet": "Packets",
    "packets": "Packets",
    "pack": "Packets",
    "பாக்கெட்": "Packets",
    "பைகள்": "Packets",
    "box": "Boxes",
    "boxes": "Boxes",
    "பெட்டி": "Boxes",
    "bag": "Bags",
    "bags": "Bags",
    "sack": "Bags",
    "sacks": "Bags",
    "மூட்டை": "Bags",
    "மூட்டைகள்": "Bags",
}

# Common Tamil case suffixes on nouns (accusative -ஐ, genitive -இன்/-உடைய, dative -க்கு, etc.)
TAMIL_SUFFIXES = [
    "யினை",
    "வினை",
    "களை",
    "களின்",
    "யின்",
    "வின்",
    "க்கு",
    "யை",
    "வை",
    "இன்",
    "ஐ",
]


def strip_tamil_suffix(term: str) -> str:
    """Strip common Tamil inflectional suffixes to aid dictionary & DB matching."""
    cleaned = term.strip().lower().rstrip("?.!,;:")
    for suffix in TAMIL_SUFFIXES:
        if len(cleaned) > len(suffix) + 1 and cleaned.endswith(suffix):
            return cleaned[: -len(suffix)].strip()
    return cleaned


def expand_search_terms(term: str) -> List[str]:
    """Return normalized search variants including Tamil/English equivalents."""
    if not term:
        return []
    raw = term.strip().lower().rstrip("?.!,;:")
    stemmed = strip_tamil_suffix(raw)
    variants = {raw, stemmed}

    for group in PRODUCT_SYNONYM_GROUPS:
        lowered_group = [g.lower() for g in group]
        if any(v in lowered_group for v in list(variants)):
            variants.update(lowered_group)
        else:
            # Also check if any group item is a stem match
            for item in lowered_group:
                if stemmed and (stemmed == item or strip_tamil_suffix(item) == stemmed):
                    variants.update(lowered_group)
                    break

    return [v for v in variants if v]


def normalize_unit_name(unit: Optional[str], fallback: str = "Pieces") -> str:
    """Normalize a spoken or user-entered unit into one of the standard catalog units."""
    if not unit:
        return fallback
    cleaned = unit.strip()
    mapped = UNIT_CANONICAL_MAP.get(cleaned.lower())
    if mapped and mapped != "Millilitres":
        return mapped
    # Preserve title-cased standard unit if already valid
    for std in TAMIL_UNIT_LABELS:
        if std.lower() == cleaned.lower():
            return std
    return fallback


def reconcile_quantity_and_unit(
    spoken_qty: Decimal,
    spoken_unit: Optional[str],
    product_unit: str,
) -> Tuple[Decimal, Optional[str]]:
    """
    Convert compatible metric sub-units (e.g., 500 Grams -> 0.5 Kilograms, 500 ml -> 0.5 Litres),
    while preserving count/container expressions (e.g., 20 bags of Rice) cleanly.
    Returns (effective_product_quantity, spoken_unit_display).
    """
    if not spoken_unit:
        return spoken_qty, None

    canon = UNIT_CANONICAL_MAP.get(spoken_unit.strip().lower(), spoken_unit.strip())

    # Metric mass conversion: Grams <-> Kilograms
    if canon == "Grams" and product_unit == "Kilograms":
        return (spoken_qty / Decimal("1000")).quantize(Decimal("0.001")), "Grams"
    if canon == "Kilograms" and product_unit == "Grams":
        return (spoken_qty * Decimal("1000")).quantize(Decimal("0.001")), "Kilograms"

    # Metric volume conversion: Millilitres -> Litres
    if canon == "Millilitres" and product_unit == "Litres":
        return (spoken_qty / Decimal("1000")).quantize(Decimal("0.001")), "ml"

    return spoken_qty, spoken_unit.strip()


def format_decimal_clean(value: Decimal) -> str:
    """Format a Decimal quantity cleanly without trailing zeros (e.g., 50.000 -> '50', 2.500 -> '2.5')."""
    quantized = Decimal(str(value))
    if quantized == quantized.to_integral_value():
        return str(int(quantized))
    normalized = quantized.normalize()
    return format(normalized, "f")


def format_money(amount: Decimal, symbol: str = "Rs.") -> str:
    """Format a Decimal monetary amount cleanly (e.g., Rs. 1,200.00 or Rs. 250.00)."""
    quantized = Decimal(str(amount)).quantize(Decimal("0.01"))
    return f"{symbol} {quantized:,.2f}"


def detect_tamil_script(text: str) -> bool:
    """Return True if text contains Tamil Unicode characters (U+0B80..U+0BFF)."""
    return any("\u0b80" <= ch <= "\u0bff" for ch in (text or ""))
