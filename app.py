from __future__ import annotations
import json, os, sqlite3, time
from typing import Any, Dict, List, Tuple
from flask import Flask, jsonify, request, send_from_directory
from engine.containment import contained_by
from engine.llm_hook import llm_containment_hint

DB_PATH = os.path.join("data", "breachit.db")

app = Flask(__name__, static_url_path="", static_folder="static")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def run_query(sql: str, params: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    conn = get_db()
    try:
        cur = conn.cursor()
        if params:
            cur.execute(sql, params)
        else:
            cur.execute(sql)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description] if cur.description else []
        results = [dict(zip(cols, r)) for r in rows]
        return results
    finally:
        conn.close()

def log_breach(authorized_id: str, user_sql: str, reason: str, superset: bool, meta: Dict[str, Any]):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO Breaches(authorized_id, user_sql, reason, is_superset, created_at, meta_json)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (authorized_id, user_sql, reason, 1 if superset else 0, int(time.time()), json.dumps(meta)))
        conn.commit()
    finally:
        conn.close()

@app.route("/")
def index():
    return app.send_static_file("index.html")

@app.get("/api/authorized")
def list_authorized():
    data = json.load(open("authorized_queries.json", "r", encoding="utf-8"))
    return jsonify(data)

@app.post("/api/submit")
def submit():
    payload = request.get_json(force=True)
    authorized_id = payload.get("authorized_id", "")
    user_sql = payload.get("user_sql", "")
    params = payload.get("params", {})

    # Load authorized query
    auth_list = json.load(open("authorized_queries.json", "r", encoding="utf-8"))
    auth = next((a for a in auth_list if a["id"] == authorized_id), None)
    if not auth:
        return jsonify({"ok": False, "error": "Unknown authorized query id."}), 400

    # Build authorized SQL with :param placeholders -> sqlite named params
    auth_sql = auth["sql"]
    allowed_tables = set(auth.get("allowed_tables", []))
    allowed_cols = set(auth.get("allowed_columns", []))

    # First: static containment checks
    static_ok, reasons = contained_by(user_sql, auth_sql, allowed_tables, allowed_cols)

    # Optional: LLM hint (stub)
    hint = llm_containment_hint(user_sql, auth_sql)  # None / True / False

    # Combine decisions (for demo, static must pass; LLM hint can only veto if False)
    if not static_ok or hint is False:
        reason = "; ".join(reasons + ([ "LLM hint: not contained" ] if hint is False else []))
        log_breach(authorized_id, user_sql, reason, False, {"params": params})
        return jsonify({"ok": False, "decision": "rejected", "reason": reason})

    # Execute both user and authorized queries to compare result sets.
    try:
        # Execute authorized query with params
        auth_res = run_query(auth_sql.replace(":", "@"), {f"@{k}": v for k, v in params.items()})
    except Exception:
        # Some Python sqlite drivers don't like ":" named params with dict—do manual format safely
        # We'll convert :param to ? in order
        auth_sql_q = auth_sql
        ordered_values = []
        for pname in auth.get("params", []):
            placeholder = f":{pname}"
            if placeholder in auth_sql_q:
                auth_sql_q = auth_sql_q.replace(placeholder, "?")
                ordered_values.append(params.get(pname))
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(auth_sql_q, tuple(ordered_values))
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description] if cur.description else []
        auth_res = [dict(zip(cols, r)) for r in rows]
        conn.close()

    # Now execute the user's query (read-only guard: refuse non-SELECT at runtime)
    try:
        # extra safety: refuse statements that are not a single SELECT
        if not user_sql.strip().lower().startswith("select"):
            raise ValueError("Only SELECT statements allowed.")
        if ";" in user_sql.strip()[1:]:
            raise ValueError("Semicolons/multiple statements not allowed.")
        user_res = run_query(user_sql)
    except Exception as e:
        reason = f"User query execution error: {e}"
        log_breach(authorized_id, user_sql, reason, False, {"params": params})
        return jsonify({"ok": False, "decision": "error", "reason": reason}), 400

    # Compare sets (tuple rows by ordered columns)
    def tupleize(rows: List[Dict[str, Any]]) -> Tuple[Tuple[Any, ...], ...]:
        if not rows:
            return tuple()
        cols = list(rows[0].keys())
        return tuple(tuple(r.get(c) for c in cols) for r in rows)

    user_set = set(tupleize(user_res))
    auth_set = set(tupleize(auth_res))

    # Subset check
    if user_set.issubset(auth_set):
        decision = "safe"
        reason = "User results are a subset (or equal) of authorized results."
        return jsonify({"ok": True, "decision": decision, "reason": reason, "user_rows": user_res, "authorized_rows": auth_res})
    else:
        # Superset or different data — likely breach
        decision = "breach"
        reason = "User results are NOT a subset of authorized results."
        log_breach(authorized_id, user_sql, reason, True, {"params": params, "authorized_sql": auth_sql})
        return jsonify({"ok": False, "decision": decision, "reason": reason, "user_rows": user_res, "authorized_rows": auth_res}), 403

if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    app.run(debug=True)
