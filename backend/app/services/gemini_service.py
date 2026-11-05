"""Google Gemini AI NLU service returning validated structured JSON intents.

Includes automatic multi-model failover, temporary 503 cooldown routing, and
high-availability deterministic NLU fallback when all cloud models experience
temporary 503/429 demand spikes.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Dict, List, Optional, Tuple

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import ValidationError

from app.models.product import Product
from app.schemas.voice import GeminiStructuredIntent
from app.utils.config import PLACEHOLDER_KEYS, refresh_runtime_env, settings
from app.utils.tamil_lexicon import PRODUCT_SYNONYM_GROUPS

logger = logging.getLogger("tamil_voice_pos.gemini")

# Cache discovered generateContent-capable Gemini models for 10 minutes
_DISCOVERED_MODELS_CACHE: Tuple[float, List[str]] = (0.0, [])
# Track models temporarily returning 503/429 -> monotonic timestamp until cooldown expires
_MODEL_COOLDOWN_UNTIL: Dict[str, float] = {}

_EXCLUDED_MODEL_KEYWORDS = (
    "embedding",
    "imagen",
    "veo",
    "tts",
    "audio",
    "vision",
    "aqa",
    "robotics",
    "computer-use",
    "image",
    "live",
    "learnlm",
    "gemma",
)

_WORD_NUMBERS: Dict[str, float] = {
    "half": 0.5,
    "quarter": 0.25,
    "one": 1,
    "a": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "twelve": 12,
    "fifteen": 15,
    "twenty": 20,
    "twenty-five": 25,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "hundred": 100,
    "ஒன்று": 1,
    "ஒரு": 1,
    "இரண்டு": 2,
    "ரெண்டு": 2,
    "மூன்று": 3,
    "மூணு": 3,
    "நான்கு": 4,
    "நாலு": 4,
    "ஐந்து": 5,
    "அஞ்சு": 5,
    "ஆறு": 6,
    "ஏழு": 7,
    "எட்டு": 8,
    "ஒன்பது": 9,
    "பத்து": 10,
    "பதினைந்து": 15,
    "இருபது": 20,
    "ஐம்பது": 50,
    "நூறு": 100,
    "அரை": 0.5,
}

_UNIT_PATTERNS: List[Tuple[str, str]] = [
    (r"\b(kilograms?|kgs?|கிலோ)\b", "Kilograms"),
    (r"\b(grams?|gm|g|கிராம்)\b", "Grams"),
    (r"\b(litres?|liters?|ltr|l|லிட்டர்)\b", "Litres"),
    (r"\b(bottles?|பாட்டில்|போத்தல்)\b", "Bottles"),
    (r"\b(packets?|packs?|பாக்கெட்)\b", "Packets"),
    (r"\b(boxes?|box|பெட்டி)\b", "Boxes"),
    (r"\b(bags?|sacks?|மூட்டை|ப்பை)\b", "Bags"),
    (r"\b(pieces?|pcs?|bars?|துண்டு|கட்டி)\b", "Pieces"),
]


class GeminiServiceError(Exception):
    """Base exception for Gemini NLU failures."""

    def __init__(self, message: str, status_code: int = 503, code: str = "GEMINI_ERROR"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


def _get_active_api_key_and_model() -> Tuple[str, str]:
    """Retrieve GEMINI_API_KEY and GEMINI_MODEL, refreshing directly from .env files on disk."""
    refresh_runtime_env()
    api_key = (settings.GEMINI_API_KEY or "").strip()
    model_name = (settings.GEMINI_MODEL or "gemini-3.8-flash").strip()

    if api_key.lower() in PLACEHOLDER_KEYS or len(api_key) < 10:
        raise GeminiServiceError(
            message=(
                "Gemini AI is not configured. Please add your GEMINI_API_KEY in backend/.env "
                "and save the file (Ctrl+S). Manual POS and inventory features remain available."
            ),
            status_code=503,
            code="GEMINI_API_KEY_MISSING",
        )

    return api_key, model_name


def _rank_model_for_failover(model_id: str) -> Tuple[int, float]:
    """
    Rank candidate models so high-availability flash-lite & flash models come first,
    sorted by version descending.
    """
    lower = model_id.lower()
    if "flash-lite" in lower or "lite" in lower:
        tier = 0
    elif "flash" in lower and "preview" not in lower and "exp" not in lower:
        tier = 1
    elif "flash" in lower:
        tier = 2
    elif "pro" in lower and "preview" not in lower and "exp" not in lower:
        tier = 3
    else:
        tier = 4

    ver_match = re.search(r"gemini-(\d+(?:\.\d+)?)", lower)
    version = float(ver_match.group(1)) if ver_match else 0.0
    return (tier, -version)


def _discover_available_models(client: genai.Client) -> List[str]:
    """Query Google Gemini API for generateContent-capable models on this API key (cached 10m)."""
    global _DISCOVERED_MODELS_CACHE
    now = time.monotonic()
    cached_at, cached_list = _DISCOVERED_MODELS_CACHE
    if cached_list and (now - cached_at) < 600:
        return cached_list

    discovered: List[str] = []
    try:
        for m in client.models.list():
            raw_name = getattr(m, "name", "") or ""
            short_name = raw_name.removeprefix("models/").strip()
            if not short_name.startswith("gemini-"):
                continue
            lower_name = short_name.lower()
            if any(kw in lower_name for kw in _EXCLUDED_MODEL_KEYWORDS):
                continue
            actions = getattr(m, "supported_actions", None)
            if actions and "generateContent" not in actions:
                continue
            discovered.append(short_name)
    except Exception as exc:
        logger.warning("Could not list Gemini models dynamically: %s", exc)

    discovered = sorted(set(discovered), key=_rank_model_for_failover)
    if discovered:
        _DISCOVERED_MODELS_CACHE = (now, discovered)
    return discovered


def _build_candidate_models(
    client: genai.Client,
    primary_model: str,
    err_message: str = "",
) -> List[str]:
    """Build ordered fallback model list excluding the failed primary model."""
    suggested = re.findall(r"models/(gemini-[a-zA-Z0-9._-]+)", err_message or "")
    discovered = _discover_available_models(client)
    static_defaults = [
        "gemini-3.8-flash-lite",
        "gemini-3.8-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.5-flash",
        "gemini-3.0-flash",
        "gemini-2.5-flash-lite",
    ]

    now = time.monotonic()
    ordered: List[str] = []
    cooling_down: List[str] = []

    for candidate in [*suggested, *discovered, *static_defaults]:
        clean = candidate.removeprefix("models/").strip()
        if not clean or clean == primary_model or clean in ordered or clean in cooling_down:
            continue
        if _MODEL_COOLDOWN_UNTIL.get(clean, 0.0) > now:
            cooling_down.append(clean)
        else:
            ordered.append(clean)

    # Limit to top 4 fallback candidates so request latency stays snappy
    return (ordered + cooling_down)[:4]


def _build_system_instruction(catalog_products: List[Product]) -> str:
    """Build strict NLU system prompt anchored on real shop catalog names."""
    catalog_lines = []
    for p in catalog_products:
        tamil_part = f" (Aliases: {p.tamil_name})" if p.tamil_name else ""
        catalog_lines.append(
            f"- {p.product_name}{tamil_part} | Category: {p.category} | Default Unit: {p.unit}"
        )
    catalog_block = "\n".join(catalog_lines) if catalog_lines else "- (Catalog currently empty)"

    return f"""You are the NLU intent parser for "Voice POS", a Point-of-Sale and Inventory Management System.
Your ONLY job is to interpret a shop owner's spoken or typed command and return structured JSON matching the required schema.

CURRENT SHOP PRODUCT CATALOG (Database Source of Truth):
{catalog_block}

SUPPORTED INTENTS:
1. CHECK_STOCK - User asks how much stock/quantity of a specific product is available (e.g., "How much rice is available?").
2. ADD_STOCK - User wants to add/restock inventory of an existing product (e.g., "Add 10 bottles of milk", "Add 20 bags of rice").
3. REDUCE_STOCK - User wants to reduce/remove/write-off damaged or used stock without recording a customer sale (e.g., "Reduce 2 kg of rice stock").
4. RECORD_SALE - User sold or wants to sell a product to a customer (e.g., "Sell 2 kilograms of sugar").
5. CHECK_PRICE - User asks the price of a product (e.g., "What is the price of soap?").
6. SEARCH_PRODUCT - User checks whether a product exists/is carried in the shop (e.g., "Do we have milk in stock?").
7. CHECK_LOW_STOCK - User asks which items are running low or out of stock (e.g., "Show low-stock products").
8. GET_TODAY_SALES - User asks for today's total sales/revenue (e.g., "What are today's sales?").
9. GET_SALES_REPORT - User asks for overall/weekly/monthly sales summary or report (e.g., "Show sales report").
10. ADD_PRODUCT - User explicitly wants to create/register a brand-new product in the catalog with a price (e.g., "Add new product Biscuit price 120").
11. UNKNOWN - Command is unrelated to shop POS/inventory, unintelligible, or cannot be understood.

STRICT RULES:
- NEVER invent products. Match `product_name` to the exact English `product_name` from the catalog when applicable, and set `spoken_product_term` to what the user said.
- If the user mentions a product NOT in the catalog, set `product_name` to their mentioned product name and `spoken_product_term` to what they said.
- NEVER invent prices (`selling_price: null` unless the user explicitly spoke a price).
- NEVER assume or invent missing quantities (`quantity: null` if the user did not state a number).
- If multiple catalog products match ambiguously, set `is_ambiguous: true` and list their catalog names in `ambiguous_candidates`.
- Always set `response_language` to `"en"`.
"""


def _extract_quantity_and_unit(text: str) -> Tuple[Optional[float], Optional[str]]:
    """Deterministically extract spoken quantity and unit without inventing missing values."""
    lower = text.lower()
    detected_unit: Optional[str] = None
    for pattern, normalized_unit in _UNIT_PATTERNS:
        if re.search(pattern, lower):
            detected_unit = normalized_unit
            break

    # Remove explicit price phrase before extracting quantity so "price 120" isn't confused
    cleaned_for_qty = re.sub(
        r"(?:price|rs\.?|lkr|விலை)\s*[:=]?\s*\d+(?:\.\d+)?",
        " ",
        lower,
    )

    num_match = re.search(r"\b(\d+(?:\.\d+)?)\b", cleaned_for_qty)
    if num_match:
        return float(num_match.group(1)), detected_unit

    for token in re.findall(r"[a-zA-Z\u0B80-\u0BFF-]+", cleaned_for_qty):
        if token in _WORD_NUMBERS:
            # Skip article "a" unless paired with a unit ("a bottle of milk")
            if token == "a" and not detected_unit:
                continue
            return _WORD_NUMBERS[token], detected_unit

    return None, detected_unit


def _match_catalog_or_spoken_product(
    text: str, catalog_products: List[Product]
) -> Tuple[Optional[str], Optional[str], bool, List[str]]:
    """Match transcript against real catalog products or extract explicit product noun."""
    lower = text.lower()
    matched: List[Tuple[str, str]] = []

    for p in catalog_products:
        terms = [p.product_name]
        if p.tamil_name:
            terms.extend([t.strip() for t in re.split(r"[/,;]+", p.tamil_name) if t.strip()])
        for group in PRODUCT_SYNONYM_GROUPS:
            if any(p.product_name.lower() == g.lower() for g in group):
                terms.extend(group)

        for term in terms:
            t_low = term.lower().strip()
            if not t_low:
                continue
            if re.search(rf"(?<![a-z0-9]){re.escape(t_low)}(?![a-z0-9])", lower):
                matched.append((p.product_name, term))
                break

    unique_names = list(dict.fromkeys(name for name, _ in matched))
    if len(unique_names) == 1:
        return matched[0][0], matched[0][1], False, []
    if len(unique_names) > 1:
        return unique_names[0], matched[0][1], True, unique_names

    # Extract explicit unknown product phrase if user asked about an uncatalogued item
    unknown_patterns = [
        r"(?:price of|cost of|stock of|have|search for|find)\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)?)",
        r"(?:how much|how many)\s+([a-zA-Z]+)\s+(?:is|are|do|in)",
        r"(?:add|sell|sold|reduce|remove)\s+(?:\d+(?:\.\d+)?\s+)?(?:[a-zA-Z]+\s+of\s+)?([a-zA-Z]+)",
    ]
    stopwords = {
        "stock",
        "available",
        "products",
        "product",
        "items",
        "item",
        "today",
        "sales",
        "low",
        "in",
        "the",
        "shop",
    }
    for pat in unknown_patterns:
        m = re.search(pat, lower)
        if m:
            candidate = m.group(1).strip()
            words = [w for w in candidate.split() if w not in stopwords]
            if words:
                noun = " ".join(words).title()
                return noun, noun, False, []

    return None, None, False, []


def _local_fallback_nlu(
    transcript: str,
    catalog_products: List[Product],
    reason: str,
) -> Tuple[GeminiStructuredIntent, str]:
    """
    Deterministic, zero-hallucination NLU fallback used ONLY when all cloud Gemini
    endpoints simultaneously fail with temporary 503 UNAVAILABLE or 429 overload.
    """
    text = (transcript or "").strip()
    lower = text.lower()

    qty, unit = _extract_quantity_and_unit(text)
    prod_name, spoken_term, is_ambig, ambig_list = _match_catalog_or_spoken_product(
        text, catalog_products
    )

    intent = "UNKNOWN"
    selling_price: Optional[float] = None

    if re.search(r"\b(today'?s?\s+sales|sales\s+today|today\s+revenue)\b|இன்றைய\s*விற்பனை", lower):
        intent = "GET_TODAY_SALES"
    elif re.search(r"\b(sales\s+report|weekly\s+sales|monthly\s+sales|report)\b|விற்பனை\s*அறிக்கை", lower):
        intent = "GET_SALES_REPORT"
    elif re.search(r"\b(low[- ]stock|running\s+low|out\s+of\s+stock|low\s+inventory)\b|குறைவாக", lower):
        intent = "CHECK_LOW_STOCK"
    elif re.search(r"\b(add\s+new\s+product|new\s+product|create\s+product)\b|புதிய\s*பொருள்", lower):
        intent = "ADD_PRODUCT"
        price_m = re.search(r"(?:price|rs\.?|lkr|at|விலை)\s*[:=]?\s*(\d+(?:\.\d+)?)", lower)
        if price_m:
            selling_price = float(price_m.group(1))
        name_m = re.search(
            r"(?:new\s+product|create\s+product)\s+([a-zA-Z0-9 ]+?)(?:\s+(?:price|at|rs|lkr|\d)|$)",
            lower,
        )
        if name_m and not prod_name:
            extracted = name_m.group(1).strip().title()
            prod_name = extracted
            spoken_term = extracted
    elif re.search(r"\b(sell|sold|record\s+sale)\b|விற்றேன்|விற்பனை\s*செய்", lower):
        intent = "RECORD_SALE"
    elif re.search(r"\b(reduce|remove|deduct|decrease)\b|குறைக்கவும்|குறை", lower):
        intent = "REDUCE_STOCK"
    elif re.search(r"\b(add|restock|top\s*up)\b|சேர்க்கவும்|சேர்", lower):
        intent = "ADD_STOCK"
    elif re.search(r"\b(price|cost|how\s+much\s+is\s+a|what\s+is\s+the\s+price)\b|விலை", lower):
        intent = "CHECK_PRICE"
    elif re.search(
        r"\b(how\s+much|how\s+many|available|stock\s+of|check\s+stock|in\s+stock)\b|எவ்வளவு",
        lower,
    ):
        if lower.startswith(("do we have", "is there", "have we got")):
            intent = "SEARCH_PRODUCT"
        else:
            intent = "CHECK_STOCK"
    elif re.search(r"\b(do\s+we\s+have|have\s+you\s+got|search|is\s+.*available)\b|இருக்கா", lower):
        intent = "SEARCH_PRODUCT"

    structured = GeminiStructuredIntent(
        intent=intent,
        product_name=prod_name,
        spoken_product_term=spoken_term,
        quantity=qty,
        unit=unit,
        selling_price=selling_price,
        confidence=0.90 if intent != "UNKNOWN" else 0.35,
        response_language="en",
        is_ambiguous=is_ambig,
        ambiguous_candidates=ambig_list,
    )
    raw_payload = structured.model_dump()
    raw_payload["_fallback_mode"] = reason
    return structured, json.dumps(raw_payload)


def interpret_voice_command(
    transcript: str,
    catalog_products: List[Product],
    hint_language: Optional[str] = None,
) -> Tuple[GeminiStructuredIntent, str]:
    """
    Send user transcript to Google Gemini and return (validated_intent, raw_json_text).
    Automatically routes around 503/429/404 model issues across available Gemini models,
    and falls back to deterministic NLU if all Gemini models are overloaded.
    """
    api_key, configured_model = _get_active_api_key_and_model()
    system_instruction = _build_system_instruction(catalog_products)

    lang_context = f"Recognition language hint: {hint_language or settings.LANGUAGE}\n"
    user_prompt = f"{lang_context}User command: {transcript}"

    try:
        client = genai.Client(api_key=api_key)
        gen_config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=GeminiStructuredIntent,
            temperature=0.1,
        )

        now = time.monotonic()
        primary_cooling = _MODEL_COOLDOWN_UNTIL.get(configured_model, 0.0) > now

        # If configured model is currently in a 60s 503 cooldown, try a healthy fallback first
        initial_model = configured_model
        if primary_cooling:
            healthy_alts = _build_candidate_models(client, configured_model)
            if healthy_alts:
                initial_model = healthy_alts[0]

        response = None
        last_api_err: Optional[genai_errors.APIError] = None

        try:
            response = client.models.generate_content(
                model=initial_model,
                contents=user_prompt,
                config=gen_config,
            )
        except genai_errors.APIError as first_err:
            last_api_err = first_err
            err_code = getattr(first_err, "code", None) or 502
            err_str = str(first_err)

            if err_code in (429, 500, 502, 503, 504):
                _MODEL_COOLDOWN_UNTIL[initial_model] = time.monotonic() + 60.0

            if err_code in (404, 429, 500, 502, 503, 504):
                candidates = _build_candidate_models(client, initial_model, err_str)
                # If we started with an alternate while primary was cooling down, include primary last
                if initial_model != configured_model and configured_model not in candidates:
                    candidates.append(configured_model)

                for fallback_model in candidates:
                    try:
                        logger.info(
                            "Gemini %s returned %s; failing over to %s",
                            initial_model,
                            err_code,
                            fallback_model,
                        )
                        response = client.models.generate_content(
                            model=fallback_model,
                            contents=user_prompt,
                            config=gen_config,
                        )
                        if err_code == 404 and initial_model == configured_model:
                            settings.GEMINI_MODEL = fallback_model
                        break
                    except genai_errors.APIError as retry_err:
                        last_api_err = retry_err
                        r_code = getattr(retry_err, "code", None) or 502
                        if r_code in (429, 500, 502, 503, 504):
                            _MODEL_COOLDOWN_UNTIL[fallback_model] = time.monotonic() + 60.0

            if response is None and last_api_err is not None:
                raise last_api_err

    except genai_errors.APIError as exc:
        err_msg = str(exc)
        code_num = getattr(exc, "code", None) or 502
        logger.error("Gemini APIError after retries (code=%s): %s", code_num, err_msg)

        if code_num in (400, 401, 403) and (
            "api key" in err_msg.lower()
            or "api_key" in err_msg.lower()
            or "permission" in err_msg.lower()
            or "unauthenticated" in err_msg.lower()
        ):
            raise GeminiServiceError(
                message="Invalid Google Gemini API key. Please verify GEMINI_API_KEY in backend/.env.",
                status_code=502,
                code="GEMINI_INVALID_API_KEY",
            ) from exc

        # High-availability fallback when ALL Gemini models are overloaded (503 / 429 / 5xx)
        if code_num in (429, 500, 502, 503, 504):
            logger.warning(
                "All Gemini cloud models overloaded (HTTP %s). Using deterministic NLU fallback.",
                code_num,
            )
            return _local_fallback_nlu(
                transcript=transcript,
                catalog_products=catalog_products,
                reason=f"GEMINI_OVERLOAD_{code_num}",
            )

        raise GeminiServiceError(
            message=f"Gemini AI service error: {err_msg}",
            status_code=502,
            code="GEMINI_API_ERROR",
        ) from exc
    except Exception as exc:
        logger.error("Gemini connection/unexpected error: %s", exc)
        raise GeminiServiceError(
            message=(
                "Unable to connect to Google Gemini AI. Please check your internet connection. "
                "Manual POS billing and inventory management continue to work normally."
            ),
            status_code=503,
            code="GEMINI_CONNECTION_ERROR",
        ) from exc

    raw_text = (response.text or "").strip()
    if not raw_text:
        return _local_fallback_nlu(
            transcript=transcript,
            catalog_products=catalog_products,
            reason="GEMINI_EMPTY_RESPONSE",
        )

    try:
        parsed_dict = json.loads(raw_text)
        structured = GeminiStructuredIntent.model_validate(parsed_dict)
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.error("Invalid structured JSON from Gemini: %s | Raw: %s", exc, raw_text)
        raise GeminiServiceError(
            message="Could not validate AI response structure. Please rephrase your command.",
            status_code=502,
            code="GEMINI_INVALID_JSON",
        ) from exc

    # Always respond in clean English for site UI display
    structured.response_language = "en"

    return structured, raw_text
