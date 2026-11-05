# Voice POS — AI-Powered Smart Retail & Inventory System

An AI-powered, voice-controlled **Point of Sale (POS) and Inventory Management System** designed for small shops, grocery stores, and SMEs.

---

## Features

- **AI Voice Command Console**: Powered by **Google Gemini** (`gemini-3.8-flash` configurable via `.env` with automatic multi-model failover) and the browser **Web Speech API** with manual text input fallback.
- **Safety-First Confirmation System**: Stock additions, stock reductions, voice sales, product deletions, and high-value bills (`> BIG_AMOUNT`) require explicit `[Confirm]` / `[Cancel]` approval tied to the authenticated user and re-validated against live SQLite inventory.
- **Native Browser Text-to-Speech**: Reads AI responses aloud using the browser `SpeechSynthesis` API, with instant Mute/Unmute and Stop controls.
- **Full-Screen Responsive POS & Thermal Receipt Printing**: Collapsible sidebar, dedicated Fullscreen mode, fast product grid & cart management, automatic LKR cash change calculation, atomic stock deduction, and printable thermal receipts.
- **Complete Product & Inventory CRUD**: Decimal-safe monetary and stock calculations (`LKR` / `Rs.`), category filtering, barcode lookup, low-stock alerts, and a full stock transaction audit ledger.
- **Dynamic Dashboard & Reports**: Live daily revenue, transaction counts, gross profit estimates, top-selling products, and category stock valuation.

---

## Technology Stack

| Layer | Technologies |
|---|---|
| **Backend** | Python 3.11, FastAPI, SQLAlchemy ORM, SQLite, Pydantic v2, PyJWT, Bcrypt, Uvicorn |
| **AI Integration** | Google Gemini API (`google-genai` SDK) with structured JSON schema validation & multi-model failover |
| **Frontend** | React 18, Vite, JavaScript (JSX), Tailwind CSS, React Router v6, Fetch API, Lucide Icons |
| **Speech** | Browser Web Speech API (`SpeechRecognition` & `SpeechSynthesis`) |

---

## Project Structure

```text
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── database.py
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── routers/
│   │   │   ├── auth.py
│   │   │   ├── products.py
│   │   │   ├── inventory.py
│   │   │   ├── sales.py
│   │   │   ├── voice.py
│   │   │   ├── reports.py
│   │   │   └── config.py
│   │   ├── services/
│   │   │   ├── gemini_service.py
│   │   │   ├── inventory_service.py
│   │   │   └── sales_service.py
│   │   └── utils/
│   ├── tests/
│   ├── .env.example
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── layouts/
│   │   ├── services/
│   │   ├── hooks/
│   │   ├── context/
│   │   ├── utils/
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── index.html
│   └── package.json
├── .env.example
├── README.md
└── .gitignore
```

---

## Installation & Local Execution

### 1. Configure Backend Environment (`backend/.env`)

Copy `backend/.env.example` to `backend/.env` and set your Google Gemini API key (obtainable from https://aistudio.google.com/apikey):

```env
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-3.8-flash

CURRENCY=LKR
LANGUAGE=en-US
LOW_STOCK_DEFAULT=5
BIG_AMOUNT=50000
```

### 2. Start the FastAPI Backend (Port 8000)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\uvicorn.exe app.main:app --reload --host 127.0.0.1 --port 8000
```

- Interactive Swagger API Docs: `http://127.0.0.1:8000/docs`
- SQLite database (`tamil_voice_pos.db`) is automatically initialized on startup with the demo account and sample products.

### 3. Start the React + Vite Frontend (Port 5173)

In a second terminal:

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

## Live Demonstration Walkthrough

Pre-seeded sample inventory:
- **Rice** — Rs. 250.00 / kg — **50 kg**
- **Sugar** — Rs. 280.00 / kg — **30 kg**
- **Milk** — Rs. 200.00 / litre — **15 litres**
- **Soap** — Rs. 150.00 / piece — **8 pieces**
- **Tea** — Rs. 1,200.00 / kg — **4 kg** *(Low-stock alert active: `4 <= 5`)*

### 7 Live Demo Scenarios
1. **Check Rice Stock:** Open **Voice Assistant** and say `"How much rice is available?"` → Reports `50 Kilograms`.
2. **Add 20 Bags of Rice:** Say `"Add 20 bags of rice"` → Assistant previews `50 → 70` → Click **Confirm** → Stock updates to `70`.
3. **Sell 2 kg of Sugar:** Say `"Sell 2 kilograms of sugar"` → Assistant previews `Rs. 560.00` bill → Click **Confirm** → Invoice generated & Sugar stock becomes `28`.
4. **Check Today's Sales:** Say `"What are today's sales?"` → Reports live daily sales total in `Rs.`.
5. **Check Low-Stock Items:** Say `"Show low-stock products"` → Lists **Tea (4 Kilograms)**.
6. **Add a New Product:** Open **Products → Add New Product** and add a new item (e.g., Coconut Oil, Rs. 900, 25 Bottles).
7. **Generate Printable POS Bill:** Open **POS / Billing**, add items to cart, enter cash received, verify automatic customer change, complete payment, and click **Print Receipt**.
