# Voice POS — Local AI Voice-Controlled POS & Inventory System

A 100% local, privacy-first, AI-powered **Point of Sale (POS) and Inventory Management System** designed for small shops and SMEs in Sri Lanka, powered exclusively by **Ollama + Qwen 2.5 3B (`qwen2.5:3b`)** running locally on user hardware.

---

## Key Features

- **100% Local AI Inference (Ollama + Qwen 2.5 3B)**: Runs completely offline/locally at `http://127.0.0.1:11434` via the official `ollama` Python library—**zero external cloud LLM APIs or API keys required**.
- **Tamil & English Natural-Language Commands**: Understands spoken and typed Tamil, Sri Lankan Tamil (`அரிசி`, `சீனி`, `பால்`, `சோப்பு`, `தேயிலை`), Tanglish, and English commands via structured JSON schema output validated by Pydantic.
- **Safety-First Confirmation Pipeline**: AI never executes SQL or modifies SQLite directly. All stock additions, reductions, voice sales, product deletions, and high-value bills (`> BIG_AMOUNT`) require explicit `[Confirm]` / `[Cancel]` approval re-validated against live database records.
- **Hardware-Optimized for RTX 4050 (6GB VRAM, 16GB RAM)**:
  - Uses quantized `qwen2.5:3b` (~1.9 GB VRAM) with compact `num_ctx=2048` and `num_predict=256`.
  - Keeps only a single model warm (`keep_alive="10m"`) and monitors GPU VRAM + System RAM live on the Settings page.
  - Automatically falls back to CPU (`num_gpu=0`) if GPU memory is insufficient.
- **Full Manual POS & Thermal Receipts**: Remains 100% operational even when Ollama is stopped.
- **Firebase Real-Time Maintenance Mode & Feature Flags**:
  - Subscribes to Firestore document `system/status` via `onSnapshot()` using the reusable `useSystemStatus` React hook so banner or full-screen blocking maintenance and per-module feature flags apply across open tabs **without page refresh**.
  - Enforces **independent HTTP `503 Service Unavailable`** protection in FastAPI (`make_maintenance_guard`) while keeping authentication (`/api/auth/*`) and administrator controls (`/api/system/*` & `/admin`) accessible.

---

## Technology Stack

| Layer | Technologies |
|---|---|
| **Backend** | Python 3.11, FastAPI, SQLAlchemy ORM, SQLite, Pydantic v2, PyJWT, Bcrypt, Uvicorn |
| **Local AI** | Ollama (`http://127.0.0.1:11434`), `ollama` Python SDK, `qwen2.5:3b` (Quantized) |
| **Frontend** | React 18, Vite, JavaScript (JSX), Tailwind CSS, React Router v6, Fetch API, Lucide Icons |
| **Real-Time Ops** | Firebase Web SDK (Firestore `system/status` `onSnapshot`) + FastAPI SSE & HTTP 503 Guard |
| **Speech** | Browser Web Speech API (`SpeechRecognition` & `SpeechSynthesis`) + Web Audio Mic Meter |

---

## 1. Local AI Model Installation (Mandatory)

Install [Ollama for Windows](https://ollama.com/download), then pull and verify **Qwen 2.5 3B** in PowerShell:

```powershell
ollama pull qwen2.5:3b
ollama run qwen2.5:3b
```

*(Type `/bye` inside the Ollama prompt to exit the interactive test; the local Ollama service continues serving at `http://127.0.0.1:11434`.)*

---

## 2. Backend Environment Configuration (`backend/.env`)

```env
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:3b
OLLAMA_TIMEOUT=60

CURRENCY=LKR
LANGUAGE=en-US
LOW_STOCK_DEFAULT=5
BIG_AMOUNT=50000
```

> **Security Note:** `OLLAMA_BASE_URL` is validated on startup to bind strictly to localhost (`127.0.0.1` / `localhost`) so Ollama's local API is never exposed to the public internet.

---

## 2b. Frontend Firebase Configuration (`frontend/.env`)

Copy `frontend/.env.example` to `frontend/.env` and populate your **public** Firebase Web App configuration:

```env
VITE_FIREBASE_API_KEY=your_firebase_web_api_key
VITE_FIREBASE_AUTH_DOMAIN=your-project-id.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your-project-id
VITE_FIREBASE_STORAGE_BUCKET=your-project-id.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=your_messaging_sender_id
VITE_FIREBASE_APP_ID=your_firebase_web_app_id
```

- **Firestore Document (`system/status`)**:
  - `maintenance` (`boolean`)
  - `message` (`string` — sanitized against HTML, SQL, file paths, and secrets)
  - `estimatedTime` (`string`)
  - `updatedAt` (`timestamp`)
  - `blocking` (`boolean` — `false` = top banner, `true` = full-screen maintenance page + FastAPI HTTP `503`)
  - `features` (`map` — `posBilling`, `voiceAssistant`, `productManagement`, `inventoryAdjustments`, `reportsAnalytics`)
- **Security Rules**: Deploy `firestore.rules` to Firebase so clients can read `system/status`, while writes are restricted exclusively to authenticated administrators (`request.auth.token.admin == true` or `role in ['admin', 'owner']`). Never place Firebase Admin SDK or service-account private keys in the frontend.
- **Graceful Fallback**: Even before `VITE_FIREBASE_*` variables are filled in, the app runs normally and synchronizes real-time maintenance state via FastAPI (`/api/system/status` + `/api/system/stream`).

---

## 3. Running the Application Locally

### Start the FastAPI Backend (Port 8000)

```powershell
cd backend
.\.venv\Scripts\uvicorn.exe app.main:app --reload --host 127.0.0.1 --port 8000
```

*(Fresh machine setup: `python -m venv .venv`, `.\.venv\Scripts\pip install -r requirements.txt`, then run Uvicorn above.)*

- Swagger API Docs: `http://127.0.0.1:8000/docs`

### Start the React + Vite Frontend (Port 5173)

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Open `http://localhost:5173` in **Google Chrome** or **Microsoft Edge**.

---

## Demo Login Credentials

- **Username:** `admin`
- **Password:** `admin123`

---

## Sample Inventory & Demo Commands

Pre-seeded sample products:
- **Rice** — Rs. 250.00 / kg — **50 kg**
- **Sugar** — Rs. 280.00 / kg — **30 kg**
- **Milk** — Rs. 200.00 / litre — **15 litres**
- **Soap** — Rs. 150.00 / piece — **8 pieces**
- **Tea** — Rs. 1,200.00 / kg — **4 kg** *(Low-stock alert active: `4 <= 5`)*

Example Tamil & English commands:
- `"How much rice is available?"` / `"கடையில் எவ்வளவு அரிசி இருக்கு?"` → `CHECK_STOCK`
- `"Add 20 bags of rice"` / `"அரிசி 20 மூட்டை சேர்க்கவும்"` → `ADD_STOCK` *(Requires Confirmation)*
- `"Sell 2 kilograms of sugar"` / `"இரண்டு கிலோ சர்க்கரை விற்றேன்"` → `RECORD_SALE` *(Requires Confirmation)*
- `"What is the price of soap?"` / `"சீனியின் விலை என்ன?"` → `CHECK_PRICE`
- `"Show low-stock products"` / `"கடையில் எந்த பொருட்கள் குறைவாக இருக்கு?"` → `CHECK_LOW_STOCK`
- `"What are today's sales?"` / `"இன்றைய விற்பனை எவ்வளவு?"` → `GET_TODAY_SALES`
