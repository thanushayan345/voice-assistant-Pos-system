"""AI Voice Assistant endpoints: process command, confirm pending operation, cancel, and history."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.product import Product
from app.models.sale import Sale
from app.models.stock_transaction import StockTransaction
from app.models.user import User
from app.models.voice_command import VoiceCommand
from app.schemas.product import ProductResponse
from app.schemas.sale import SaleItemCreate
from app.schemas.voice import (
    AIStructuredIntent,
    VoiceCancelRequest,
    VoiceCommandResponse,
    VoiceConfirmRequest,
    VoiceHistoryItem,
    VoiceProcessRequest,
)
from app.services.ollama_service import (
    OllamaServiceError,
    interpret_voice_command,
)
from app.services.inventory_service import (
    adjust_stock,
    get_active_product_or_404,
    get_low_stock_products,
    resolve_product_candidates,
)
from app.services.sales_service import (
    create_sale_transaction,
    get_today_sales_metrics,
    local_day_utc_bounds,
    serialize_sale,
)
from app.utils.config import settings
from app.utils.security import get_current_user
from app.utils.tamil_lexicon import (
    TAMIL_UNIT_LABELS,
    format_decimal_clean,
    format_money,
    normalize_unit_name,
    reconcile_quantity_and_unit,
)

router = APIRouter(prefix="/api/voice", tags=["Voice Assistant"])

CONFIRMATION_TTL_MINUTES = 10


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _display_product_bilingual(product: Product, lang: str) -> str:
    if lang == "ta" and product.tamil_name:
        primary_tamil = product.tamil_name.split("/")[0].strip()
        return f"{primary_tamil} ({product.product_name})"
    return product.product_name


def _display_unit_bilingual(unit: str, lang: str) -> str:
    if lang == "ta":
        return TAMIL_UNIT_LABELS.get(unit, unit)
    return unit


def _resolve_single_product(
    db: Session,
    product_name: Optional[str],
    spoken_term: Optional[str],
    is_ambiguous: bool,
    ambiguous_candidates: List[str],
    lang: str,
) -> Tuple[Optional[Product], Optional[str], Optional[Dict[str, Any]]]:
    """
    Resolve an unambiguous database Product or return a bilingual clarification/error message.
    Returns (product, error_or_clarification_msg, extra_data).
    """
    label_used = (spoken_term or product_name or "").strip()
    if not label_used:
        msg = (
            "எந்தப் பொருள் என்பதைத் தயவுசெய்து குறிப்பிடவும்."
            if lang == "ta"
            else "Please specify which product you are referring to."
        )
        return None, msg, None

    if is_ambiguous and len(ambiguous_candidates) > 1:
        joined = ", ".join(ambiguous_candidates)
        msg = (
            f"பல பொருட்கள் பொருந்துகின்றன ({joined}). எந்தப் பொருள் என்று தெளிவுபடுத்தவும்."
            if lang == "ta"
            else f"Multiple products match ({joined}). Please clarify which product you mean."
        )
        return None, msg, {"candidates": ambiguous_candidates}

    matches = resolve_product_candidates(db, product_name, spoken_term)
    if not matches:
        msg = (
            f"மன்னிக்கவும், '{label_used}' என்ற பொருள் கடை பட்டியலில் இல்லை."
            if lang == "ta"
            else f"Sorry, '{label_used}' was not found in the shop product catalog."
        )
        return None, msg, {"queried_term": label_used}

    if len(matches) > 1:
        names = [p.product_name for p in matches]
        joined = ", ".join(names)
        msg = (
            f"'{label_used}' என்பதற்கு பல பொருட்கள் உள்ளன: {joined}. துல்லியமான பெயரைக் கூறவும்."
            if lang == "ta"
            else f"Multiple products matched '{label_used}': {joined}. Please specify the exact product."
        )
        return None, msg, {"candidates": names}

    return matches[0], None, None


@router.post("/process", response_model=VoiceCommandResponse)
def process_voice_command(
    payload: VoiceProcessRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Full 11-step Local AI Voice Processing Pipeline:
    Receives recognized text -> Calls local Ollama (qwen2.5:3b) for structured JSON -> Validates against SQLite DB ->
    Executes read-only queries OR creates user-bound pending confirmation for stock/sale changes.
    """
    now_utc = datetime.now(timezone.utc)
    recent_cutoff = now_utc - timedelta(seconds=5)

    # Duplicate command safeguard: return existing pending confirmation if identical command sent within 5s
    existing_pending = (
        db.query(VoiceCommand)
        .filter(
            VoiceCommand.user_id == current_user.id,
            VoiceCommand.status == "PENDING_CONFIRMATION",
            VoiceCommand.transcript == payload.transcript,
        )
        .order_by(VoiceCommand.id.desc())
        .first()
    )
    if existing_pending and _ensure_utc(existing_pending.created_at) >= recent_cutoff:
        stored_data = (
            json.loads(existing_pending.validated_payload)
            if existing_pending.validated_payload
            else {}
        )
        return VoiceCommandResponse(
            command_id=existing_pending.id,
            intent=existing_pending.intent,
            transcript=existing_pending.transcript,
            response_text=existing_pending.response_text or "",
            response_language="en",
            confidence=float(existing_pending.confidence or 0),
            requires_confirmation=True,
            confirmation_token=existing_pending.confirmation_token,
            status=existing_pending.status,
            is_big_amount_warning=bool(stored_data.get("is_big_amount_warning", False)),
            data=stored_data.get("preview"),
            created_at=existing_pending.created_at,
        )

    catalog_products = (
        db.query(Product)
        .filter(Product.is_deleted.is_(False))
        .order_by(Product.product_name.asc())
        .all()
    )

    try:
        ai_result, raw_json = interpret_voice_command(
            transcript=payload.transcript,
            catalog_products=catalog_products,
            hint_language=payload.language,
        )
    except OllamaServiceError as exc:
        failed_cmd = VoiceCommand(
            user_id=current_user.id,
            transcript=payload.transcript,
            language=payload.language or settings.LANGUAGE,
            intent="UNKNOWN",
            status="FAILED",
            requires_confirmation=False,
            response_text=exc.message,
        )
        db.add(failed_cmd)
        db.commit()
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc

    return _execute_interpreted_voice_intent(
        db=db,
        current_user=current_user,
        transcript=payload.transcript,
        language=payload.language,
        ai_result=ai_result,
        raw_json=raw_json,
        now_utc=now_utc,
    )


def _execute_interpreted_voice_intent(
    db: Session,
    current_user: User,
    transcript: str,
    language: Optional[str],
    ai_result: AIStructuredIntent,
    raw_json: str,
    now_utc: datetime,
) -> VoiceCommandResponse:
    lang = "en"
    intent = ai_result.intent
    sym = settings.currency_symbol
    confidence = round(float(ai_result.confidence or 0.0), 3)

    response_text = ""
    requires_confirmation = False
    confirmation_token: Optional[str] = None
    cmd_status = "COMPLETED"
    validated_payload: Optional[Dict[str, Any]] = None
    response_data: Optional[Dict[str, Any]] = None
    is_big_warning = False

    # ---------------- READ-ONLY INTENTS ----------------
    if intent == "GET_TODAY_SALES":
        today_total, today_count = get_today_sales_metrics(db)
        money_str = format_money(today_total, sym)
        if lang == "ta":
            response_text = (
                f"இன்றைய மொத்த விற்பனை {money_str} ({today_count} விற்பனைப் பட்டியல்கள்)."
            )
        else:
            response_text = (
                f"Today's total sales are {money_str} across {today_count} transaction(s)."
            )
        response_data = {
            "today_total_sales": float(today_total),
            "today_transactions_count": today_count,
            "currency": settings.CURRENCY,
        }

    elif intent == "GET_SALES_REPORT":
        start_today, _ = local_day_utc_bounds()
        seven_days_ago = start_today - timedelta(days=6)
        recent_sales = db.query(Sale).filter(Sale.created_at >= seven_days_ago).all()
        week_total = sum(
            (Decimal(str(s.total_amount)) for s in recent_sales),
            Decimal("0.00"),
        ).quantize(Decimal("0.01"))
        today_total, today_count = get_today_sales_metrics(db)
        if lang == "ta":
            response_text = (
                f"கடந்த 7 நாட்களின் மொத்த விற்பனை {format_money(week_total, sym)} "
                f"({len(recent_sales)} பரிவர்த்தனைகள்). இன்றைய விற்பனை: {format_money(today_total, sym)}."
            )
        else:
            response_text = (
                f"Last 7 days sales total {format_money(week_total, sym)} across "
                f"{len(recent_sales)} transaction(s). Today's sales: {format_money(today_total, sym)} ({today_count} bill(s))."
            )
        response_data = {
            "seven_day_total_sales": float(week_total),
            "seven_day_transactions": len(recent_sales),
            "today_total_sales": float(today_total),
            "today_transactions_count": today_count,
        }

    elif intent == "CHECK_LOW_STOCK":
        low_items = get_low_stock_products(db)
        if not low_items:
            response_text = (
                "தற்போது எந்தப் பொருளும் குறைவான இருப்பில் இல்லை. அனைத்து பொருட்களும் போதுமான அளவு உள்ளன."
                if lang == "ta"
                else "Great news! No products are currently running low on stock."
            )
        else:
            if lang == "ta":
                parts = [
                    f"{_display_product_bilingual(p, 'ta')}: {format_decimal_clean(Decimal(str(p.stock_quantity)))} {_display_unit_bilingual(p.unit, 'ta')}"
                    for p in low_items
                ]
                response_text = f"குறைவான இருப்பில் உள்ள பொருட்கள் ({len(low_items)}): " + ", ".join(parts) + "."
            else:
                parts = [
                    f"{p.product_name} ({format_decimal_clean(Decimal(str(p.stock_quantity)))} {p.unit})"
                    for p in low_items
                ]
                response_text = f"Low-stock products ({len(low_items)}): " + ", ".join(parts) + "."
        response_data = {
            "low_stock_count": len(low_items),
            "products": [ProductResponse.model_validate(p).model_dump(mode="json") for p in low_items],
        }

    elif intent == "SEARCH_PRODUCT":
        query_term = (ai_result.spoken_product_term or ai_result.product_name or "").strip()
        matches = resolve_product_candidates(db, ai_result.product_name, ai_result.spoken_product_term)
        if not matches:
            response_text = (
                f"இல்லை, '{query_term}' தற்போது கடையில் இல்லை."
                if lang == "ta"
                else f"No, '{query_term}' is not currently in the shop catalog."
            )
            response_data = {"found": False, "queried_term": query_term, "products": []}
        else:
            p = matches[0]
            qty_dec = Decimal(str(p.stock_quantity))
            qty_str = format_decimal_clean(qty_dec)
            price_str = format_money(Decimal(str(p.selling_price)), sym)
            if qty_dec > Decimal("0"):
                response_text = (
                    f"ஆம், {_display_product_bilingual(p, 'ta')} கடையில் உள்ளது. "
                    f"இருப்பு: {qty_str} {_display_unit_bilingual(p.unit, 'ta')}, விலை: {price_str}."
                    if lang == "ta"
                    else f"Yes, {p.product_name} is available! Stock: {qty_str} {p.unit}, Price: {price_str}/{p.unit}."
                )
            else:
                response_text = (
                    f"{_display_product_bilingual(p, 'ta')} பட்டியலில் உள்ளது, ஆனால் தற்போது இருப்பு காலியாக உள்ளது (0)."
                    if lang == "ta"
                    else f"{p.product_name} is in the catalog, but it is currently out of stock (0 {p.unit})."
                )
            response_data = {
                "found": True,
                "products": [ProductResponse.model_validate(m).model_dump(mode="json") for m in matches],
            }

    elif intent == "CHECK_STOCK":
        product, err_msg, extra = _resolve_single_product(
            db,
            ai_result.product_name,
            ai_result.spoken_product_term,
            ai_result.is_ambiguous,
            ai_result.ambiguous_candidates,
            lang,
        )
        if not product:
            response_text = err_msg or ""
            response_data = extra
        else:
            qty_dec = Decimal(str(product.stock_quantity))
            qty_str = format_decimal_clean(qty_dec)
            low_note_ta = " (குறைவான இருப்பு!)" if product.is_low_stock else ""
            low_note_en = " (Low stock alert!)" if product.is_low_stock else ""
            response_text = (
                f"கடையில் {_display_product_bilingual(product, 'ta')} {qty_str} "
                f"{_display_unit_bilingual(product.unit, 'ta')} இருப்பு உள்ளது.{low_note_ta}"
                if lang == "ta"
                else f"{product.product_name} available stock: {qty_str} {product.unit}.{low_note_en}"
            )
            response_data = {
                "product": ProductResponse.model_validate(product).model_dump(mode="json")
            }

    elif intent == "CHECK_PRICE":
        product, err_msg, extra = _resolve_single_product(
            db,
            ai_result.product_name,
            ai_result.spoken_product_term,
            ai_result.is_ambiguous,
            ai_result.ambiguous_candidates,
            lang,
        )
        if not product:
            response_text = err_msg or ""
            response_data = extra
        else:
            price_str = format_money(Decimal(str(product.selling_price)), sym)
            response_text = (
                f"{_display_product_bilingual(product, 'ta')} விலை ஒரு "
                f"{_display_unit_bilingual(product.unit, 'ta')}-க்கு {price_str}."
                if lang == "ta"
                else f"The selling price of {product.product_name} is {price_str} per {product.unit}."
            )
            response_data = {
                "product": ProductResponse.model_validate(product).model_dump(mode="json")
            }

    # ---------------- MUTATING INTENTS (ALWAYS REQUIRE CONFIRMATION) ----------------
    elif intent in ("ADD_STOCK", "REDUCE_STOCK", "RECORD_SALE"):
        product, err_msg, extra = _resolve_single_product(
            db,
            ai_result.product_name,
            ai_result.spoken_product_term,
            ai_result.is_ambiguous,
            ai_result.ambiguous_candidates,
            lang,
        )
        if not product:
            response_text = err_msg or ""
            response_data = extra
        elif ai_result.quantity is None:
            response_text = (
                f"{_display_product_bilingual(product, 'ta')} எவ்வளவு அளவு என்று தயவுசெய்து குறிப்பிடவும்."
                if lang == "ta"
                else f"Please specify the quantity for {product.product_name}."
            )
        else:
            try:
                raw_qty = Decimal(str(ai_result.quantity)).quantize(
                    Decimal("0.001"), rounding=ROUND_HALF_UP
                )
            except (InvalidOperation, ValueError):
                raw_qty = Decimal("0")

            if raw_qty <= Decimal("0"):
                response_text = (
                    "சரியான அளவை (பூஜ்ஜியத்திற்கு மேல்) குறிப்பிடவும்."
                    if lang == "ta"
                    else "Please provide a valid quantity greater than zero."
                )
            else:
                effective_qty, spoken_unit_display = reconcile_quantity_and_unit(
                    raw_qty, ai_result.unit, product.unit
                )
                current_stock = Decimal(str(product.stock_quantity)).quantize(Decimal("0.001"))

                if intent in ("REDUCE_STOCK", "RECORD_SALE") and current_stock < effective_qty:
                    avail_str = format_decimal_clean(current_stock)
                    req_str = format_decimal_clean(effective_qty)
                    response_text = (
                        f"போதுமான இருப்பு இல்லை! {_display_product_bilingual(product, 'ta')} "
                        f"தற்போது {avail_str} {_display_unit_bilingual(product.unit, 'ta')} மட்டுமே உள்ளது "
                        f"(கேட்கப்பட்டது: {req_str})."
                        if lang == "ta"
                        else f"Insufficient stock! Only {avail_str} {product.unit} of {product.product_name} "
                        f"is available (requested: {req_str} {product.unit})."
                    )
                    response_data = {
                        "insufficient_stock": True,
                        "available_stock": float(current_stock),
                        "requested_quantity": float(effective_qty),
                        "product": ProductResponse.model_validate(product).model_dump(mode="json"),
                    }
                else:
                    requires_confirmation = True
                    cmd_status = "PENDING_CONFIRMATION"
                    confirmation_token = uuid.uuid4().hex

                    eff_qty_str = format_decimal_clean(effective_qty)
                    raw_qty_str = format_decimal_clean(raw_qty)
                    spoken_u_ta = (
                        TAMIL_UNIT_LABELS.get(
                            normalize_unit_name(spoken_unit_display, fallback=""),
                            spoken_unit_display or _display_unit_bilingual(product.unit, "ta"),
                        )
                        if spoken_unit_display
                        else _display_unit_bilingual(product.unit, "ta")
                    )
                    spoken_u_en = spoken_unit_display or product.unit

                    if intent == "ADD_STOCK":
                        projected_stock = current_stock + effective_qty
                        proj_str = format_decimal_clean(projected_stock)
                        curr_str = format_decimal_clean(current_stock)
                        response_text = (
                            f"{raw_qty_str} {spoken_u_ta} {_display_product_bilingual(product, 'ta')} "
                            f"இருப்பில் சேர்க்கவா? (இருப்பு: {curr_str} → {proj_str} {product.unit})"
                            if lang == "ta"
                            else f"Confirm adding {raw_qty_str} {spoken_u_en} of {product.product_name} to stock? "
                            f"(Stock: {curr_str} → {proj_str} {product.unit})"
                        )
                        preview_info = {
                            "operation": "ADD_STOCK",
                            "product_id": product.product_id,
                            "product_name": product.product_name,
                            "tamil_name": product.tamil_name,
                            "quantity": float(effective_qty),
                            "unit": product.unit,
                            "spoken_unit": spoken_unit_display,
                            "current_stock": float(current_stock),
                            "projected_stock": float(projected_stock),
                        }
                    elif intent == "REDUCE_STOCK":
                        projected_stock = current_stock - effective_qty
                        proj_str = format_decimal_clean(projected_stock)
                        curr_str = format_decimal_clean(current_stock)
                        response_text = (
                            f"{raw_qty_str} {spoken_u_ta} {_display_product_bilingual(product, 'ta')} "
                            f"இருப்பிலிருந்து குறைக்கவா? (இருப்பு: {curr_str} → {proj_str} {product.unit})"
                            if lang == "ta"
                            else f"Confirm reducing {raw_qty_str} {spoken_u_en} of {product.product_name} from stock? "
                            f"(Stock: {curr_str} → {proj_str} {product.unit})"
                        )
                        preview_info = {
                            "operation": "REDUCE_STOCK",
                            "product_id": product.product_id,
                            "product_name": product.product_name,
                            "tamil_name": product.tamil_name,
                            "quantity": float(effective_qty),
                            "unit": product.unit,
                            "current_stock": float(current_stock),
                            "projected_stock": float(projected_stock),
                        }
                    else:  # RECORD_SALE
                        unit_price = Decimal(str(product.selling_price)).quantize(Decimal("0.01"))
                        sale_total = (effective_qty * unit_price).quantize(
                            Decimal("0.01"), rounding=ROUND_HALF_UP
                        )
                        projected_stock = current_stock - effective_qty
                        total_str = format_money(sale_total, sym)
                        big_limit = Decimal(str(settings.BIG_AMOUNT)).quantize(Decimal("0.01"))
                        is_big_warning = sale_total > big_limit

                        big_prefix_ta = (
                            f"உயர் மதிப்பு விற்பனை எச்சரிக்கை ({total_str})! "
                            if is_big_warning
                            else ""
                        )
                        big_prefix_en = (
                            f"High-value sale alert ({total_str})! "
                            if is_big_warning
                            else ""
                        )
                        response_text = (
                            f"{big_prefix_ta}{eff_qty_str} {_display_unit_bilingual(product.unit, 'ta')} "
                            f"{_display_product_bilingual(product, 'ta')} விற்பனையைப் பதிவு செய்யவா? "
                            f"மொத்தத் தொகை: {total_str}."
                            if lang == "ta"
                            else f"{big_prefix_en}Confirm recording sale of {eff_qty_str} {product.unit} "
                            f"{product.product_name} for {total_str}?"
                        )
                        preview_info = {
                            "operation": "RECORD_SALE",
                            "product_id": product.product_id,
                            "product_name": product.product_name,
                            "tamil_name": product.tamil_name,
                            "quantity": float(effective_qty),
                            "unit": product.unit,
                            "unit_price": float(unit_price),
                            "total_amount": float(sale_total),
                            "current_stock": float(current_stock),
                            "projected_stock": float(projected_stock),
                        }

                    validated_payload = {
                        "intent": intent,
                        "product_id": product.product_id,
                        "effective_quantity": str(effective_qty),
                        "spoken_unit": spoken_unit_display,
                        "response_language": lang,
                        "is_big_amount_warning": is_big_warning,
                        "preview": preview_info,
                    }
                    response_data = preview_info

    elif intent == "ADD_PRODUCT":
        new_name = (ai_result.product_name or ai_result.spoken_product_term or "").strip()
        if not new_name:
            response_text = (
                "புதிய பொருளின் பெயரைக் குறிப்பிடவும்."
                if lang == "ta"
                else "Please state the name of the new product to add."
            )
        elif ai_result.selling_price is None or ai_result.selling_price <= 0:
            response_text = (
                f"'{new_name}' பொருளைச் சேர்க்க அதன் விற்பனை விலையைக் குறிப்பிடவும்."
                if lang == "ta"
                else f"Please specify the selling price in {settings.CURRENCY} to add '{new_name}'."
            )
        else:
            existing = resolve_product_candidates(db, new_name, None)
            exact_dup = any(p.product_name.lower() == new_name.lower() for p in existing)
            if exact_dup:
                response_text = (
                    f"'{new_name}' ஏற்கனவே கடை பட்டியலில் உள்ளது."
                    if lang == "ta"
                    else f"'{new_name}' already exists in the product catalog."
                )
            else:
                sell_dec = Decimal(str(ai_result.selling_price)).quantize(Decimal("0.01"))
                buy_dec = (
                    Decimal(str(ai_result.purchase_price)).quantize(Decimal("0.01"))
                    if ai_result.purchase_price and ai_result.purchase_price >= 0
                    else sell_dec
                )
                init_qty = (
                    Decimal(str(ai_result.quantity)).quantize(Decimal("0.001"))
                    if ai_result.quantity and ai_result.quantity > 0
                    else Decimal("0.000")
                )
                std_unit = normalize_unit_name(ai_result.unit, fallback="Pieces")
                cat = (ai_result.category or "General").strip()

                requires_confirmation = True
                cmd_status = "PENDING_CONFIRMATION"
                confirmation_token = uuid.uuid4().hex

                price_str = format_money(sell_dec, sym)
                qty_str = format_decimal_clean(init_qty)
                response_text = (
                    f"புதிய பொருள் '{new_name}' (விலை: {price_str}/{std_unit}, ஆரம்ப இருப்பு: {qty_str}) சேர்க்கவா?"
                    if lang == "ta"
                    else f"Confirm adding new product '{new_name}' at {price_str}/{std_unit} (Initial stock: {qty_str})?"
                )
                preview_info = {
                    "operation": "ADD_PRODUCT",
                    "product_name": new_name,
                    "tamil_name": ai_result.spoken_product_term if lang == "ta" else None,
                    "category": cat,
                    "selling_price": float(sell_dec),
                    "purchase_price": float(buy_dec),
                    "stock_quantity": float(init_qty),
                    "unit": std_unit,
                }
                validated_payload = {
                    "intent": "ADD_PRODUCT",
                    "product_name": new_name,
                    "tamil_name": ai_result.spoken_product_term if lang == "ta" else None,
                    "category": cat,
                    "selling_price": str(sell_dec),
                    "purchase_price": str(buy_dec),
                    "stock_quantity": str(init_qty),
                    "unit": std_unit,
                    "response_language": lang,
                    "is_big_amount_warning": False,
                    "preview": preview_info,
                }
                response_data = preview_info

    else:  # UNKNOWN
        response_text = (
            "மன்னிக்கவும், அந்தக் கட்டளையைப் புரிந்துகொள்ள முடியவில்லை. "
            "உதாரணம்: 'கடையில் எவ்வளவு அரிசி இருக்கு?' அல்லது 'இரண்டு கிலோ சர்க்கரை விற்றேன்'."
            if lang == "ta"
            else "Sorry, I couldn't understand that command. "
            "Try saying: 'How much rice is available?', 'Add 20 bags of rice', or 'Sell 2 kg of sugar'."
        )

    voice_cmd = VoiceCommand(
        confirmation_token=confirmation_token,
        user_id=current_user.id,
        transcript=transcript,
        language=language or settings.LANGUAGE,
        intent=intent,
        ai_raw_response=raw_json,
        validated_payload=json.dumps(validated_payload) if validated_payload else None,
        confidence=Decimal(str(confidence)),
        requires_confirmation=requires_confirmation,
        status=cmd_status,
        response_text=response_text,
        resolved_at=None if requires_confirmation else now_utc,
    )
    db.add(voice_cmd)
    db.commit()
    db.refresh(voice_cmd)

    return VoiceCommandResponse(
        command_id=voice_cmd.id,
        intent=intent,
        transcript=voice_cmd.transcript,
        response_text=response_text,
        response_language=lang,
        confidence=confidence,
        requires_confirmation=requires_confirmation,
        confirmation_token=confirmation_token,
        status=voice_cmd.status,
        is_big_amount_warning=is_big_warning,
        data=response_data,
        created_at=voice_cmd.created_at,
    )


@router.post("/confirm", response_model=VoiceCommandResponse)
def confirm_voice_command(
    payload: VoiceConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Re-validate and execute a pending voice operation owned by the authenticated user.
    Never trusts parameters from the frontend; reads server-stored validated_payload.
    """
    voice_cmd = (
        db.query(VoiceCommand)
        .filter(VoiceCommand.confirmation_token == payload.confirmation_token)
        .first()
    )
    if not voice_cmd or voice_cmd.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pending confirmation not found for this user.",
        )

    if voice_cmd.status != "PENDING_CONFIRMATION":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"This command has already been {voice_cmd.status.lower()}.",
        )

    now_utc = datetime.now(timezone.utc)
    if now_utc - _ensure_utc(voice_cmd.created_at) > timedelta(minutes=CONFIRMATION_TTL_MINUTES):
        voice_cmd.status = "EXPIRED"
        voice_cmd.resolved_at = now_utc
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation expired. Please issue the voice command again.",
        )

    if not voice_cmd.validated_payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid pending command state.",
        )

    stored = json.loads(voice_cmd.validated_payload)
    intent = stored["intent"]
    lang = "en"
    sym = settings.currency_symbol
    result_data: Dict[str, Any] = {}

    if intent in ("ADD_STOCK", "REDUCE_STOCK"):
        product = get_active_product_or_404(db, int(stored["product_id"]))
        eff_qty = Decimal(stored["effective_quantity"])
        adj_type = "ADD" if intent == "ADD_STOCK" else "REDUCE"
        spoken_u = stored.get("spoken_unit")
        reason_note = f"Voice AI confirmed ({voice_cmd.transcript[:80]})"
        if spoken_u:
            reason_note += f" [spoken unit: {spoken_u}]"

        updated_product = adjust_stock(
            db=db,
            product_id=product.product_id,
            adjustment_type=adj_type,
            quantity=eff_qty,
            user_id=current_user.id,
            reason=reason_note,
            commit=False,
        )
        new_qty_str = format_decimal_clean(Decimal(str(updated_product.stock_quantity)))
        eff_str = format_decimal_clean(eff_qty)

        if intent == "ADD_STOCK":
            done_text = (
                f"வெற்றிகரமாக சேர்க்கப்பட்டது! {_display_product_bilingual(updated_product, 'ta')} "
                f"புதிய இருப்பு: {new_qty_str} {_display_unit_bilingual(updated_product.unit, 'ta')}."
                if lang == "ta"
                else f"Stock updated! Added {eff_str} {updated_product.unit} to {updated_product.product_name}. "
                f"New stock: {new_qty_str} {updated_product.unit}."
            )
        else:
            done_text = (
                f"இருப்பு குறைக்கப்பட்டது! {_display_product_bilingual(updated_product, 'ta')} "
                f"தற்போதைய இருப்பு: {new_qty_str} {_display_unit_bilingual(updated_product.unit, 'ta')}."
                if lang == "ta"
                else f"Stock reduced! Remaining {updated_product.product_name} stock: "
                f"{new_qty_str} {updated_product.unit}."
            )

        voice_cmd.status = "CONFIRMED"
        voice_cmd.response_text = done_text
        voice_cmd.resolved_at = now_utc
        db.commit()
        db.refresh(updated_product)
        result_data = {
            "product": ProductResponse.model_validate(updated_product).model_dump(mode="json")
        }

    elif intent == "RECORD_SALE":
        product = get_active_product_or_404(db, int(stored["product_id"]))
        eff_qty = Decimal(stored["effective_quantity"])
        unit_price = Decimal(str(product.selling_price)).quantize(Decimal("0.01"))
        exact_total = (eff_qty * unit_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        sale = create_sale_transaction(
            db=db,
            user=current_user,
            items=[SaleItemCreate(product_id=product.product_id, quantity=eff_qty)],
            cash_received=exact_total,
            payment_method="CASH",
            source="VOICE",
            notes=f"Voice command: {voice_cmd.transcript[:120]}",
            confirm_big_amount=True,
        )
        db.refresh(product)
        rem_str = format_decimal_clean(Decimal(str(product.stock_quantity)))
        total_str = format_money(exact_total, sym)
        done_text = (
            f"விற்பனை பதிவு செய்யப்பட்டது ({sale.invoice_number})! "
            f"மொத்தம்: {total_str}. {_display_product_bilingual(product, 'ta')} மீதமுள்ள இருப்பு: "
            f"{rem_str} {_display_unit_bilingual(product.unit, 'ta')}."
            if lang == "ta"
            else f"Sale recorded ({sale.invoice_number})! Total: {total_str}. "
            f"Remaining {product.product_name} stock: {rem_str} {product.unit}."
        )
        voice_cmd.status = "CONFIRMED"
        voice_cmd.response_text = done_text
        voice_cmd.resolved_at = now_utc
        db.commit()
        result_data = {
            "sale": serialize_sale(sale).model_dump(mode="json"),
            "product": ProductResponse.model_validate(product).model_dump(mode="json"),
        }

    elif intent == "ADD_PRODUCT":
        p_name = stored["product_name"]
        dup = (
            db.query(Product)
            .filter(Product.is_deleted.is_(False), Product.product_name.ilike(p_name))
            .first()
        )
        if dup:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Product '{p_name}' already exists.",
            )
        init_qty = Decimal(stored["stock_quantity"])
        new_prod = Product(
            product_name=p_name,
            tamil_name=stored.get("tamil_name"),
            category=stored.get("category", "General"),
            purchase_price=Decimal(stored["purchase_price"]),
            selling_price=Decimal(stored["selling_price"]),
            stock_quantity=init_qty,
            unit=stored.get("unit", "Pieces"),
            low_stock_limit=Decimal(str(settings.LOW_STOCK_DEFAULT)),
            is_deleted=False,
        )
        db.add(new_prod)
        db.flush()

        if init_qty > Decimal("0"):
            db.add(
                StockTransaction(
                    product_id=new_prod.product_id,
                    user_id=current_user.id,
                    transaction_type="INITIAL",
                    quantity=init_qty,
                    previous_stock=Decimal("0.000"),
                    new_stock=init_qty,
                    reason="Created via Voice AI command",
                )
            )
        done_text = (
            f"புதிய பொருள் '{new_prod.product_name}' வெற்றிகரமாக சேர்க்கப்பட்டது!"
            if lang == "ta"
            else f"New product '{new_prod.product_name}' has been added to the catalog!"
        )
        voice_cmd.status = "CONFIRMED"
        voice_cmd.response_text = done_text
        voice_cmd.resolved_at = now_utc
        db.commit()
        db.refresh(new_prod)
        result_data = {
            "product": ProductResponse.model_validate(new_prod).model_dump(mode="json")
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported confirmation intent: {intent}",
        )

    return VoiceCommandResponse(
        command_id=voice_cmd.id,
        intent=voice_cmd.intent,
        transcript=voice_cmd.transcript,
        response_text=voice_cmd.response_text or "",
        response_language=lang,
        confidence=float(voice_cmd.confidence or 0),
        requires_confirmation=False,
        confirmation_token=None,
        status=voice_cmd.status,
        is_big_amount_warning=False,
        data=result_data,
        created_at=voice_cmd.created_at,
    )


@router.post("/cancel", response_model=VoiceCommandResponse)
def cancel_voice_command(
    payload: VoiceCancelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancel a pending voice command without modifying the database."""
    voice_cmd = (
        db.query(VoiceCommand)
        .filter(VoiceCommand.confirmation_token == payload.confirmation_token)
        .first()
    )
    if not voice_cmd or voice_cmd.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pending confirmation not found for this user.",
        )

    if voice_cmd.status != "PENDING_CONFIRMATION":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Command is already {voice_cmd.status.lower()}.",
        )

    stored = (
        json.loads(voice_cmd.validated_payload) if voice_cmd.validated_payload else {}
    )
    lang = "en"

    cancel_msg = (
        "செயல்பாடு இரத்து செய்யப்பட்டது. இருப்பில் எந்த மாற்றமும் செய்யப்படவில்லை."
        if lang == "ta"
        else "Operation cancelled. No changes were made to inventory or sales."
    )

    voice_cmd.status = "CANCELLED"
    voice_cmd.response_text = cancel_msg
    voice_cmd.resolved_at = datetime.now(timezone.utc)
    db.commit()

    return VoiceCommandResponse(
        command_id=voice_cmd.id,
        intent=voice_cmd.intent,
        transcript=voice_cmd.transcript,
        response_text=cancel_msg,
        response_language=lang,
        confidence=float(voice_cmd.confidence or 0),
        requires_confirmation=False,
        confirmation_token=None,
        status="CANCELLED",
        is_big_amount_warning=False,
        data=None,
        created_at=voice_cmd.created_at,
    )


@router.get("/history", response_model=List[VoiceHistoryItem])
def get_voice_history(
    limit: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return recent voice commands issued by the authenticated user."""
    rows = (
        db.query(VoiceCommand)
        .filter(VoiceCommand.user_id == current_user.id)
        .order_by(VoiceCommand.created_at.desc(), VoiceCommand.id.desc())
        .limit(limit)
        .all()
    )
    return [
        VoiceHistoryItem(
            id=r.id,
            transcript=r.transcript,
            intent=r.intent,
            status=r.status,
            confidence=float(r.confidence) if r.confidence is not None else None,
            response_text=r.response_text,
            created_at=r.created_at,
        )
        for r in rows
    ]
