# BreachIt — SQL Query Containment Testing Prototype

A minimal working prototype for an educational SQL-injection containment tester.

## What this includes
- **Flask** backend (Python 3.10+) with SQLite
- A **multi-relation schema** (Users, Products, Orders, OrderItems, Reviews)
- **Authorized query templates** with parameters
- A **containment engine** (rule-based) + **LLM hook** (stub) to simulate/replace with an actual model
- A small **web UI** (vanilla HTML/JS) to submit arbitrary SQL and compare against an authorized query
- **Breach logging** (records suspected SQL injection attempts + details)

## Quick start

### 1. Create and activate a virtual environment (recommended)
```bash
cd BreachIt
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Initialize the database (creates schema + seed data)
```bash
python seed_db.py
```

### 4. Run the server
```bash
python app.py
```

The app will start at **http://127.0.0.1:5000/**.

## How it works

1. Pick an **authorized query** from the dropdown on the web page.
2. Enter your **arbitrary SQL** (must be a single `SELECT`).
3. The **Containment Engine** tries to determine if your query is contained
   within the selected authorized query using:
   - Simple **static checks** (tables, columns, no UNION/; etc.)
   - A pluggable **LLM hook** (`engine/llm_hook.py`) which is a stub you can replace with a real LLM call.
4. If contained, your SQL is executed.
5. Results from your SQL are compared to the **authorized query's** result set:
   - If your results are a **subset** of the authorized results → **Safe**.
   - If your results are a **superset** → **Breach** (logged to `breaches` table).

> ⚠️ **Educational prototype:** This is NOT a production-grade SQL firewall. The rule-based checks are simplified.
> For real systems use proper parameterization, least-privilege DB accounts, and vetted policies.

## Files & folders

```
BreachIt/
├─ app.py                        # Flask server
├─ seed_db.py                    # Creates schema + seed data
├─ requirements.txt
├─ engine/
│  ├─ __init__.py
│  ├─ containment.py             # Rule-based containment checks
│  └─ llm_hook.py                # Stub for LLM-based reasoning (replace with real call)
├─ authorized_queries.json       # List of authorized queries with params
├─ static/
│  ├─ index.html                 # Simple UI
│  └─ main.js
└─ data/
   └─ breachit.db                # SQLite DB (created by seed script)
```

## Replacing the LLM stub
Edit `engine/llm_hook.py` and implement `llm_containment_hint(...)` to call your provider
(OpenAI, Azure, local model, etc.) and return a boolean or a confidence score that the user query
is a subset of the authorized one. The server combines this with static checks.

## License
MIT — for educational use.
