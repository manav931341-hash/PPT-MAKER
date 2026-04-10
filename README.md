# ⚡ FileForge AI — Goal-to-File Agent

> **Natural language → Professional PPTX & Excel in seconds.**
> Built for Hackathon 2025 · Powered by Claude AI

[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.36-red?logo=streamlit)](https://streamlit.io)
[![MySQL](https://img.shields.io/badge/MySQL-8.0-orange?logo=mysql)](https://mysql.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## 🎯 What It Does

You describe what you need in plain English. FileForge AI:

1. Detects whether you need a **PPTX**, **Excel**, or **both**
2. Generates **3 structural options** — you pick or customise
3. Presents **10 visual themes × 4 tones** — you choose
4. Fills every slide/sheet with **AI-generated content**
5. Builds and delivers the real file — download instantly
6. Lets you **chat to refine** anything post-generation

---

## ✨ Features

| Feature | Details |
|---|---|
| **10 PPTX Themes** | Professional, Creative, Startup, Ocean, Nature, Gold, Sunset, Rose Gold, Monochrome, Minimal |
| **19 Slide Layouts** | Title Hero, Two-Column, Chart+Text, Timeline, Stats Highlight, Icon Grid, Quote, Data Table, and 11 more |
| **8 Excel Themes** | Corporate Blue, Dark Modern, Forest Green, Ocean Data, Purple Pro, and more |
| **Real Charts** | Matplotlib-rendered Bar, Line, Pie, Area, Scatter — embedded in files |
| **Unsplash Backgrounds** | AI-selected real photography for image slides |
| **Rich Excel** | Conditional formatting, data bars, traffic lights, heat maps, frozen headers, native charts |
| **Upload Reference** | Upload a sample PPTX/Excel to replicate its style |
| **Iterative Refinement** | Chat after generation — files regenerate with your changes |
| **Parallel Generation** | PPTX and Excel generated simultaneously for "Both" mode |
| **MySQL Persistence** | User accounts, session history, generation logs, API keys |
| **SSE Streaming** | Live status updates during generation |
| **API Key Auth** | Every endpoint protected by API key middleware |

---

## 🏗 Architecture

```
User (Browser frontend OR Streamlit)
         │
         ▼
┌─────────────────────────────────┐
│     FastAPI  (main.py)          │  ← REST API + SSE streaming
│  /auth  /start  /respond        │
│  /refine  /download  /stream    │
└───────────────┬─────────────────┘
                │
                ▼
┌─────────────────────────────────┐
│  GoalToFileAgent  (agent.py)    │  ← State machine
│  C1→C2→C3→C4→C5→DONE          │
│  + refine_with_chat()           │
└────┬──────────────┬─────────────┘
     │              │
     ▼              ▼
┌─────────┐  ┌───────────────────┐
│  Claude │  │  File Generators  │
│  API    │  │  pptx_generator   │
│(claude- │  │  xlsx_generator   │
│opus-4)  │  └───────────────────┘
└─────────┘
     │
     ▼
┌─────────────────────────────────┐
│  MySQL Database (database.py)   │
│  users · sessions · history     │
│  api_keys                       │
└─────────────────────────────────┘
```

### State Machine
```
C1_INTENT → C2_STRUCTURE → C3_STYLE → C4_CONTENT → C5_FILE → DONE
     ↑                                                    │
     └──────────── refine_with_chat() ◄──────────────────┘
```

---

## 📁 Project Structure

```
fileforge-ai/
│
├── 📄 main.py                   # FastAPI backend — all routes
├── 🤖 agent.py                  # Core state machine + LLM calls
├── 💾 database.py               # MySQL CRUD — users, sessions, history
├── 📝 models.py                 # Pydantic request/response models
├── 💬 prompts.py                # All LLM prompts + design library (10 themes, 19 layouts)
├── 🖥  streamlit_app.py         # Streamlit UI (alternative to HTML frontend)
├── 🧪 example_calls.py         # End-to-end API test script
├── 📦 requirements.txt
├── 🔧 .env.example
│
├── generators/
│   ├── __init__.py
│   ├── 🎨 pptx_generator.py    # python-pptx builder — all themes & layouts
│   └── 📊 xlsx_generator.py    # openpyxl builder — all styles & formatting
│
├── parsers/
│   ├── __init__.py
│   └── 🔍 reference_parser.py  # Extracts structure from uploaded PPTX/XLSX
│
└── frontend/
    └── 🌐 index.html           # Production-grade SPA frontend
```

---

## ⚙️ Setup Guide

### Prerequisites
- Python 3.11+
- MySQL 8.0+
- Anthropic API key
- (Optional) Unsplash API key

---

### Step 1 — Clone the Repository

```bash
git clone https://github.com/yourusername/fileforge-ai.git
cd fileforge-ai
```

---

### Step 2 — Create MySQL Database

Open MySQL and run:

```sql
CREATE DATABASE goal_to_file CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

The tables (`users`, `sessions`, `generation_history`, `api_keys`) are created **automatically** when you first start the backend.

---

### Step 3 — Configure Environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Required
ANTHROPIC_API_KEY=sk-ant-your-key-here
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your-mysql-password
MYSQL_DB=goal_to_file

# Optional (free at unsplash.com/developers)
UNSPLASH_ACCESS_KEY=your-unsplash-key

# App
OUTPUT_DIR=./outputs
API_BASE=http://localhost:8000
```

---

### Step 4 — Install Dependencies

```bash
pip install -r requirements.txt
```

---

### Step 5 — Start the FastAPI Backend

```bash
uvicorn main:app --reload --port 8000
```

You should see:
```
✅ Database tables initialised.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

API docs at: **http://localhost:8000/docs**

---

### Step 6 — Open the Frontend

**Option A — HTML Frontend (Recommended)**

Simply open `frontend/index.html` in your browser. No server needed.

> ⚠️ If you run into CORS issues, serve it with:
> ```bash
> cd frontend && python -m http.server 3000
> ```
> Then open **http://localhost:3000**

**Option B — Streamlit UI**

```bash
streamlit run streamlit_app.py
```

Open **http://localhost:8501**

---

### Step 7 — Test the Full Flow

```bash
python example_calls.py
```

This runs 4 end-to-end tests: PPTX, Excel, Both, and Refinement.

---

## 🔌 API Reference

### Auth

| Method | Endpoint | Description |
|---|---|---|
| POST | `/auth/register` | Create account → returns API key |
| POST | `/auth/login` | Login → returns API key |

### Generator Flow

| Method | Endpoint | Description |
|---|---|---|
| POST | `/start` | Start generation with a goal |
| POST | `/respond` | Send checkpoint response |
| POST | `/refine/{session_id}` | Chat-based refinement post-generation |
| POST | `/upload-reference/{session_id}` | Upload PPTX/XLSX reference file |

### Files & Data

| Method | Endpoint | Description |
|---|---|---|
| GET | `/download/{session_id}/{filename}` | Download generated file |
| GET | `/session/{session_id}` | Get session state |
| GET | `/history/{user_id}` | Get generation history |
| GET | `/sessions/{user_id}` | Get all user sessions |
| GET | `/stream/{session_id}` | SSE live status stream |

### Auth Header

All protected endpoints require:
```
X-Api-Key: gtf-your-api-key-here
```

---

## 📊 How Generation Works

### Checkpoint Flow

```
POST /start  →  C1: Intent Detection
                  ↓ User confirms file type
              C2: Structure Planning (3 options)
                  ↓ User picks A/B/C or custom
              C3: Style Selection (themes + tone)
                  ↓ User picks theme + tone
              C4: Content Generation (full slides/sheets)
                  ↓ User approves / modifies
              C5: File Build (parallel if "both")
                  ↓
              Download ready
                  ↓
POST /refine  →  Chat-based refinement loop (unlimited)
```

### Design Library (in prompts.py)

The LLM picks from a **pre-defined design library** — it never invents colours or layouts freely. This guarantees quality:

- **10 PPTX colour themes** (Professional, Creative, Startup, Ocean, etc.)
- **5 font pairs** (Montserrat+Lato, Playfair+Lato, Raleway+OpenSans, etc.)
- **19 slide layout templates** (title_hero, bullets_header, two_col_equal, chart_full, timeline, stats_highlight, etc.)
- **8 background styles** (solid, gradient, image_overlay, accent_band, diagonal split)
- **8 Excel themes** with full column style specs
- **12 Excel features** (data_bars, traffic_lights, heatmap, sparklines, etc.)

---

## 🖥 Frontend Pages

| Page | Route | Description |
|---|---|---|
| Landing | `#landing` | Hero, features, pricing, how it works |
| Dashboard | `#dashboard` | Overview, projects, history, settings |
| AI Generator | `#generator` | Full checkpoint flow with progress steps |
| Slide Editor | `#editor` | Visual editor with AI chat assistant |
| Excel Generator | `#excel` | Spreadsheet prompt + preview |
| Templates | `#templates` | 20 templates across 7 categories |
| Analytics | `#analytics` | Usage charts and stats |

---

## 🗄 Database Schema

```sql
-- Users
CREATE TABLE users (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  username      VARCHAR(80)  NOT NULL UNIQUE,
  email         VARCHAR(200) NOT NULL UNIQUE,
  password_hash VARCHAR(128) NOT NULL,
  created_at    DATETIME     DEFAULT CURRENT_TIMESTAMP
);

-- Sessions (full agent state per generation)
CREATE TABLE sessions (
  session_id   VARCHAR(64)  PRIMARY KEY,
  user_id      INT          NOT NULL,
  goal         TEXT,
  state        VARCHAR(40),
  file_type    VARCHAR(10),
  style        VARCHAR(40),
  structure    JSON,
  content      JSON,
  created_at   DATETIME,
  updated_at   DATETIME
);

-- Every file ever generated
CREATE TABLE generation_history (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  user_id      INT,
  session_id   VARCHAR(64),
  file_type    VARCHAR(10),
  filename     VARCHAR(200),
  goal         TEXT,
  theme        VARCHAR(40),
  created_at   DATETIME
);

-- API keys (1 per user)
CREATE TABLE api_keys (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  user_id    INT  NOT NULL UNIQUE,
  api_key    VARCHAR(64) NOT NULL UNIQUE,
  created_at DATETIME
);
```

---

## 🔗 Connecting Frontend ↔ Backend ↔ Database

### Complete Connection Flow

```
Browser (index.html)
    │
    │  fetch('http://localhost:8000/start', {method:'POST', body:JSON})
    │  Header: X-Api-Key: gtf-...
    │
    ▼
FastAPI (main.py)  :8000
    │
    ├── API Key → get_user_by_api_key() → MySQL users + api_keys tables
    ├── Route /start → agent.start(goal, user_id)
    │
    ▼
agent.py (state machine)
    │
    ├── _llm() → Anthropic Claude API (claude-opus-4-5)
    ├── save_session() → MySQL sessions table
    │
    ▼
generators/
    ├── pptx_generator.py → python-pptx → .pptx file → ./outputs/{session_id}/
    └── xlsx_generator.py → openpyxl   → .xlsx file → ./outputs/{session_id}/
    │
    ▼
database.py
    └── log_generation() → MySQL generation_history table
    │
    ▼
FastAPI returns JSON → {files: [{filename, download_url}]}
    │
    ▼
Browser downloads file via /download/{session_id}/{filename}
```

---

## 🔒 Security Notes

- Passwords are SHA-256 hashed before storage
- API keys are random 64-char hex tokens, prefixed `gtf-`
- All protected routes require `X-Api-Key` header
- CORS is currently open (`*`) — restrict to your domain in production
- Session files are stored in `./outputs/` — restrict access in production

---

## 📋 File Paste Order for VS Code

Paste/create files in this **exact order** to avoid import errors:

```
1.  requirements.txt        ← install first
2.  .env.example            ← copy to .env and fill in keys
3.  database.py             ← no internal imports
4.  models.py               ← no internal imports
5.  prompts.py              ← no internal imports
6.  generators/__init__.py  ← empty file
7.  generators/pptx_generator.py
8.  generators/xlsx_generator.py
9.  parsers/__init__.py     ← empty file
10. parsers/reference_parser.py
11. agent.py                ← imports database, prompts, generators
12. main.py                 ← imports agent, models, database, parsers
13. streamlit_app.py        ← imports nothing from project (uses HTTP)
14. example_calls.py        ← test script
15. frontend/index.html     ← open in browser (no server needed)
```

**Create these folders manually before pasting:**
```
mkdir generators
mkdir parsers
mkdir frontend
mkdir outputs
```

---

## 🚀 Quick Start (TL;DR)

```bash
# 1. Clone
git clone https://github.com/yourusername/fileforge-ai.git && cd fileforge-ai

# 2. MySQL
mysql -u root -p -e "CREATE DATABASE goal_to_file;"

# 3. Environment
cp .env.example .env  # then edit with your keys

# 4. Install
pip install -r requirements.txt

# 5. Backend
uvicorn main:app --reload --port 8000

# 6. Open frontend
open frontend/index.html   # macOS
# or: start frontend/index.html  (Windows)
# or: xdg-open frontend/index.html  (Linux)

# 7. Test
python example_calls.py
```

---

## 🛠 Troubleshooting

| Problem | Solution |
|---|---|
| `mysql.connector` connection refused | Check MySQL is running: `sudo service mysql start` |
| `ANTHROPIC_API_KEY not set` | Add key to `.env` file or export it |
| CORS errors in browser | Serve `index.html` via `python -m http.server 3000` |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` again |
| Empty files generated | Check `outputs/` folder permissions: `chmod 755 outputs/` |
| Unsplash not working | UNSPLASH_ACCESS_KEY not set — image slides will use solid colour fallback |

---

## 🔮 Roadmap

- [ ] Redis session caching for scale
- [ ] WebSocket real-time streaming
- [ ] PDF export support
- [ ] Google Slides integration
- [ ] Team workspaces
- [ ] Custom brand templates
- [ ] AI image generation (Replicate/Stability AI)
- [ ] Mobile app

---

## 👥 Team

Built with ❤️ for Hackathon 2025.

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
