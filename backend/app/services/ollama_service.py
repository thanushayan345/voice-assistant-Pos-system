"""Local Ollama (qwen2.5:3b) AI NLU service with RTX 4050 GPU optimization & CPU fallback.

Strictly local inference via the official `ollama` Python library at http://127.0.0.1:11434.
Never calls external cloud LLM APIs and never directly modifies SQLite records.
"""

from __future__ import annotations

import ctypes
import json
import logging
import subprocess
from typing import Any, Dict, List, Optional, Tuple

import httpx
import ollama
from pydantic import ValidationError

from app.models.product import Product
from app.schemas.config import HardwareMetrics
from app.schemas.voice import AIStructuredIntent
from app.utils.config import refresh_runtime_env, settings

logger = logging.getLogger("tamil_voice_pos.ollama")

# Tuned for NVIDIA RTX 4050 (6GB VRAM) + 16GB system RAM with quantized qwen2.5:3b (~1.9GB)
GPU_OPTIMIZED_OPTIONS: Dict[str, Any] = {
    "temperature": 0.1,
    "num_ctx": 2048,
    "num_predict": 256,
    "top_p": 0.9,
}

CPU_FALLBACK_OPTIONS: Dict[str, Any] = {
    **GPU_OPTIMIZED_OPTIONS,
    "num_gpu": 0,
}

VRAM_OOM_KEYWORDS = (
    "cuda",
    "out of memory",
    "vram",
    "ggml_cuda",
    "failed to allocate",
    "insufficient memory",
    "cublas",
)


class OllamaServiceError(Exception):
    """Raised when local Ollama inference or validation fails."""

    def __init__(self, message: str, status_code: int = 503, code: str = "OLLAMA_ERROR"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


class _MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def _get_system_ram_metrics() -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Read Windows physical RAM usage via Win32 GlobalMemoryStatusEx without extra deps."""
    try:
        if hasattr(ctypes, "windll"):
            stat = _MemoryStatusEx()
            stat.dwLength = ctypes.sizeof(_MemoryStatusEx)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                total_gb = round(stat.ullTotalPhys / (1024**3), 2)
                avail_gb = stat.ullAvailPhys / (1024**3)
                used_gb = round(max(0.0, total_gb - avail_gb), 2)
                return total_gb, used_gb, float(stat.dwMemoryLoad)
    except Exception:
        pass
    return None, None, None


def _get_nvidia_gpu_metrics() -> Tuple[Optional[str], Optional[int], Optional[int]]:
    """Query NVIDIA GPU name and VRAM usage via nvidia-smi when available."""
    try:
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.used",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=1.5,
            creationflags=creationflags,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            first_line = proc.stdout.strip().splitlines()[0]
            parts = [p.strip() for p in first_line.split(",")]
            if len(parts) >= 3:
                return parts[0], int(float(parts[1])), int(float(parts[2]))
    except Exception:
        pass
    return None, None, None


def _extract_model_names(list_response: Any) -> List[str]:
    """Normalize model names returned across ollama-python versions."""
    models_raw = (
        getattr(list_response, "models", None)
        if not isinstance(list_response, dict)
        else list_response.get("models", [])
    ) or []
    names: List[str] = []
    for item in models_raw:
        if isinstance(item, dict):
            name = item.get("model") or item.get("name") or ""
        else:
            name = getattr(item, "model", None) or getattr(item, "name", None) or ""
        if name:
            names.append(str(name))
    return names


def _model_matches(configured: str, installed_names: List[str]) -> bool:
    target = configured.strip().lower()
    target_base = target.split(":")[0]
    for name in installed_names:
        low = name.strip().lower()
        if low == target:
            return True
        if ":" not in configured and low.split(":")[0] == target_base:
            return True
    return False


def get_ollama_and_hardware_status() -> Tuple[bool, bool, HardwareMetrics]:
    """
    Probe local Ollama daemon at OLLAMA_BASE_URL + local GPU/RAM metrics.
    Returns (ollama_connected, ollama_model_ready, hardware_metrics).
    """
    refresh_runtime_env()
    ram_total, ram_used, ram_pct = _get_system_ram_metrics()
    gpu_name, vram_total, vram_used = _get_nvidia_gpu_metrics()

    accel = f"GPU Ready ({gpu_name})" if gpu_name else "CPU / Auto"
    loaded_vram_mb: Optional[float] = None
    ollama_connected = False
    model_ready = False

    try:
        client = ollama.Client(host=settings.OLLAMA_BASE_URL, timeout=1.8)
        listed = client.list()
        ollama_connected = True
        installed_names = _extract_model_names(listed)
        model_ready = _model_matches(settings.OLLAMA_MODEL, installed_names)

        try:
            ps_resp = client.ps()
            running_models = (
                getattr(ps_resp, "models", None)
                if not isinstance(ps_resp, dict)
                else ps_resp.get("models", [])
            ) or []
            for rm in running_models:
                r_name = (
                    rm.get("model") or rm.get("name")
                    if isinstance(rm, dict)
                    else getattr(rm, "model", None) or getattr(rm, "name", None)
                ) or ""
                if _model_matches(settings.OLLAMA_MODEL, [str(r_name)]):
                    size_vram = (
                        rm.get("size_vram", 0)
                        if isinstance(rm, dict)
                        else getattr(rm, "size_vram", 0)
                    ) or 0
                    loaded_vram_mb = round(float(size_vram) / (1024**2), 1)
                    if loaded_vram_mb > 0:
                        accel = f"GPU Active ({loaded_vram_mb} MB VRAM)"
                    else:
                        accel = "CPU Fallback Active (RAM)"
                    break
        except Exception:
            pass
    except Exception:
        ollama_connected = False
        model_ready = False

    metrics = HardwareMetrics(
        gpu_name=gpu_name,
        vram_total_mb=vram_total,
        vram_used_mb=vram_used,
        ram_total_gb=ram_total,
        ram_used_gb=ram_used,
        ram_percent=ram_pct,
        loaded_model_vram_mb=loaded_vram_mb,
        acceleration=accel,
    )
    return ollama_connected, model_ready, metrics


def _build_system_instruction(catalog_products: List[Product]) -> str:
    """Build compact, high-accuracy Tamil + English NLU prompt optimized for qwen2.5:3b (2K ctx)."""
    catalog_lines = []
    for p in catalog_products:
        tamil_part = f" (Tamil/Aliases: {p.tamil_name})" if p.tamil_name else ""
        catalog_lines.append(
            f"- {p.product_name}{tamil_part} | Category: {p.category} | Unit: {p.unit}"
        )
    catalog_block = "\n".join(catalog_lines) if catalog_lines else "- (Catalog empty)"

    return f"""You are the NLU intent parser for "Tamil Voice POS", a Sri Lankan Point-of-Sale and Inventory system.
Extract the user's intent and entities from Tamil, Tanglish, or English commands and return ONLY valid JSON matching the schema.

SHOP CATALOG (Source of Truth):
{catalog_block}

INTENTS:
- CHECK_STOCK: Ask available stock of a product ("கடையில் எவ்வளவு அரிசி இருக்கு?", "How much rice is available?")
- ADD_STOCK: Add/restock inventory ("அரிசி 20 மூட்டை சேர்க்கவும்", "Add 10 bottles of milk")
- REDUCE_STOCK: Reduce/remove damaged stock without a sale ("பால் 2 லிட்டர் குறைக்கவும்", "Reduce 2 kg of rice")
- RECORD_SALE: Sell product to customer ("இரண்டு கிலோ சர்க்கரை விற்றேன்", "Sell 2 kilograms of sugar")
- CHECK_PRICE: Ask selling price ("சீனியின் விலை என்ன?", "What is the price of soap?")
- SEARCH_PRODUCT: Check if product exists ("சோப்பு இருக்கா?", "Do we have milk in stock?")
- CHECK_LOW_STOCK: Ask which products are low on stock ("கடையில் எந்த பொருட்கள் குறைவாக இருக்கு?", "Show low-stock products")
- GET_TODAY_SALES: Ask today's total sales ("இன்றைய விற்பனை எவ்வளவு?", "What are today's sales?")
- GET_SALES_REPORT: Ask overall/weekly sales report ("விற்பனை அறிக்கை காட்டு", "Show sales report")
- ADD_PRODUCT: Create a new catalog product with explicit price ("புதிய பொருள் பிஸ்கட் விலை 120 சேர்க்கவும்", "Add new product Biscuit price 120")
- UNKNOWN: Unrelated or unintelligible command.

STRICT RULES:
1. Match Tamil & Sri Lankan Tamil terms to exact catalog English `product_name`:
   அரிசி -> "Rice", சர்க்கரை / சீனி -> "Sugar", பால் -> "Milk", சோப்பு / சவர்க்காரம் -> "Soap", தேயிலை / டீ -> "Tea".
   Keep `spoken_product_term` as the word spoken by the user.
2. NEVER invent products, prices (`selling_price: null` unless spoken), or missing quantities (`quantity: null` if not spoken).
3. Tamil numbers: ஒன்று/ஒரு=1, இரண்டு/ரெண்டு=2, மூன்று=3, நான்கு=4, ஐந்து=5, பத்து=10, இருபது=20, ஐம்பது=50, நூறு=100, அரை=0.5.
4. Units: மூட்டை/bags->"Bags", கிலோ/kg->"Kilograms", கிராம்/g->"Grams", லிட்டர்/litres->"Litres", போத்தல்/பாட்டில்/bottles->"Bottles", பாக்கெட்/packets->"Packets", துண்டு/pieces->"Pieces".
5. Set `confidence` between 0.0 and 1.0 (e.g. 0.95 for clear commands). Set `response_language` to "en"."""


def _extract_message_content(response: Any) -> str:
    if isinstance(response, dict):
        return str((response.get("message") or {}).get("content") or "").strip()
    msg = getattr(response, "message", None)
    return str(getattr(msg, "content", "") or "").strip()


def interpret_voice_command(
    transcript: str,
    catalog_products: List[Product],
    hint_language: Optional[str] = None,
) -> Tuple[AIStructuredIntent, str]:
    """
    Interpret a Tamil or English POS voice command locally via Ollama (qwen2.5:3b).
    Uses GPU acceleration by default on RTX 4050 and falls back to CPU if VRAM is exhausted.
    """
    refresh_runtime_env()
    if settings.AI_PROVIDER.lower() != "ollama":
        raise OllamaServiceError(
            message="Only local Ollama AI is permitted by system configuration.",
            status_code=500,
            code="INVALID_AI_PROVIDER",
        )

    model_name = settings.OLLAMA_MODEL
    base_url = settings.OLLAMA_BASE_URL
    timeout_sec = settings.OLLAMA_TIMEOUT

    system_prompt = _build_system_instruction(catalog_products)
    lang_hint = hint_language or settings.LANGUAGE
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"Language hint: {lang_hint}\nCommand: {transcript}",
        },
    ]
    json_schema = AIStructuredIntent.model_json_schema()

    client = ollama.Client(host=base_url, timeout=timeout_sec)

    try:
        try:
            response = client.chat(
                model=model_name,
                messages=messages,
                format=json_schema,
                options=GPU_OPTIMIZED_OPTIONS,
                keep_alive="10m",
            )
        except ollama.ResponseError as gpu_err:
            err_lower = str(gpu_err).lower()
            status_code = getattr(gpu_err, "status_code", 500)
            if status_code == 404 or "not found" in err_lower:
                raise OllamaServiceError(
                    message=(
                        f"Local Ollama model '{model_name}' is not installed yet. "
                        f"Run `ollama pull {model_name}` in PowerShell, then try again. "
                        f"Manual POS and inventory features remain available."
                    ),
                    status_code=503,
                    code="OLLAMA_MODEL_MISSING",
                ) from gpu_err

            # Automatic CPU fallback when RTX 4050 6GB VRAM is insufficient
            if any(k in err_lower for k in VRAM_OOM_KEYWORDS):
                logger.warning(
                    "GPU VRAM limit reached for %s (%s). Retrying on CPU fallback (num_gpu=0).",
                    model_name,
                    gpu_err,
                )
                response = client.chat(
                    model=model_name,
                    messages=messages,
                    format=json_schema,
                    options=CPU_FALLBACK_OPTIONS,
                    keep_alive="5m",
                )
            else:
                raise OllamaServiceError(
                    message=f"Local Ollama error ({model_name}): {gpu_err}",
                    status_code=502,
                    code="OLLAMA_RESPONSE_ERROR",
                ) from gpu_err

    except OllamaServiceError:
        raise
    except (httpx.ConnectError, ConnectionError, OSError) as conn_exc:
        logger.error("Cannot reach local Ollama at %s: %s", base_url, conn_exc)
        raise OllamaServiceError(
            message=(
                f"Cannot connect to local Ollama at {base_url}. "
                f"Please start Ollama (`ollama serve` or open the Ollama app) and ensure "
                f"`ollama pull {model_name}` has been completed. Manual POS billing and inventory remain fully functional."
            ),
            status_code=503,
            code="OLLAMA_UNAVAILABLE",
        ) from conn_exc
    except httpx.TimeoutException as timeout_exc:
        logger.error("Local Ollama timed out after %ss: %s", timeout_sec, timeout_exc)
        raise OllamaServiceError(
            message=(
                f"Local Ollama model '{model_name}' timed out after {timeout_sec}s while loading weights. "
                f"Please try your command again now that the model is warming up, or increase OLLAMA_TIMEOUT in backend/.env."
            ),
            status_code=504,
            code="OLLAMA_TIMEOUT",
        ) from timeout_exc
    except Exception as exc:
        logger.error("Unexpected local Ollama failure: %s", exc)
        raise OllamaServiceError(
            message=(
                f"Local Ollama AI service is unavailable ({exc}). "
                f"Manual POS and inventory operations continue to work normally."
            ),
            status_code=503,
            code="OLLAMA_UNAVAILABLE",
        ) from exc

    raw_text = _extract_message_content(response)
    if not raw_text:
        raise OllamaServiceError(
            message=f"Local model '{model_name}' returned an empty response. Please repeat your command.",
            status_code=502,
            code="OLLAMA_EMPTY_RESPONSE",
        )

    try:
        parsed_dict = json.loads(raw_text)
        structured = AIStructuredIntent.model_validate(parsed_dict)
    except (json.JSONDecodeError, ValidationError) as val_exc:
        logger.error("Invalid JSON from %s: %s | Raw: %s", model_name, val_exc, raw_text)
        raise OllamaServiceError(
            message="Could not validate local AI JSON output. Please rephrase your command clearly.",
            status_code=502,
            code="OLLAMA_INVALID_JSON",
        ) from val_exc

    structured.response_language = "en"
    return structured, raw_text
