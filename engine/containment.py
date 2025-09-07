from __future__ import annotations
from typing import Dict, List, Tuple, Any, Set
import re

SAFE_SELECT_RE = re.compile(r"^\s*select\s", re.IGNORECASE | re.DOTALL)

FORBIDDEN_TOKENS = [
    ";", "--", "/*", "*/", "drop", "insert", "update", "delete", "alter", "create", "attach", "pragma", "vacuum",
    "grant", "revoke", "truncate"
]

UNION_RE = re.compile(r"\bunion\b", re.IGNORECASE)
JOIN_RE = re.compile(r"\bjoin\b", re.IGNORECASE)

IDENT_RE = r"[A-Za-z_][A-Za-z0-9_]*"
TABLE_EXTRACT_RE = re.compile(r"from\s+(" + IDENT_RE + r")(?:\s+\w+)?", re.IGNORECASE)
TABLES_EXTRACT_RE = re.compile(r"from\s+(" + IDENT_RE + r")(?:\s+\w+)?(?:\s*,\s*(" + IDENT_RE + r")(?:\s+\w+)?)?", re.IGNORECASE)
SELECT_COLS_RE = re.compile(r"select\s+(.*?)\s+from", re.IGNORECASE | re.DOTALL)

def tokenize_identifiers(expr: str) -> Set[str]:
    return set(re.findall(IDENT_RE, expr))

def basic_static_safety_checks(sql: str) -> Tuple[bool, List[str]]:
    """
    Very simple static checks to ensure:
    - Single SELECT only
    - No dangerous tokens
    - No UNIONs
    """
    reasons = []
    s = sql.strip()
    if not SAFE_SELECT_RE.match(s):
        reasons.append("Only single SELECT statements are allowed.")
    lowered = s.lower()
    for tok in FORBIDDEN_TOKENS:
        if tok in lowered:
            reasons.append(f"Forbidden token detected: {tok}")
    if UNION_RE.search(lowered):
        reasons.append("UNION is not allowed.")
    if ";" in s.strip()[1:]:
        reasons.append("Multiple statements or semicolons are not allowed.")

    return (len(reasons) == 0, reasons)

def extract_tables(sql: str) -> Set[str]:
    """
    Extract up to two tables from simple FROM clause: FROM t1 [, t2]
    """
    m = TABLES_EXTRACT_RE.search(sql)
    if not m:
        return set()
    return {t for t in m.groups() if t}

def extract_columns(sql: str) -> Set[str]:
    m = SELECT_COLS_RE.search(sql)
    if not m:
        return set()
    cols = m.group(1)
    if cols.strip() == "*":
        return {"*"}
    # normalize split by commas
    parts = [p.strip() for p in cols.split(",")]
    # keep simple identifiers (allow t.col too)
    norm = set()
    for p in parts:
        if "." in p:
            norm.add(p.lower())
        else:
            norm.add(p.lower())
    return norm

def where_clause(sql: str) -> str:
    m = re.search(r"\bwhere\b(.*?)(?:\bgroup\b|\border\b|$)", sql, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else ""

def normalized_space(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()

def implies_subset(user_where: str, auth_where: str) -> bool:
    """
    Heuristic: if the user's WHERE clause contains all the auth WHERE tokens, we *guess* subset.
    This is a naive string containment check intended only for demo purposes.
    """
    u = normalized_space(user_where)
    a = normalized_space(auth_where)
    if not a:
        # If authorized has no WHERE, user's must also have none for subset
        return u == ""
    # All tokens from auth must appear in user
    auth_tokens = set(a.split())
    user_tokens = set(u.split())
    return auth_tokens.issubset(user_tokens)

def contained_by(user_sql: str, auth_sql: str, allowed_tables: Set[str], allowed_cols: Set[str]) -> Tuple[bool, List[str]]:
    """
    Combine checks:
    - static safety
    - table subset
    - column subset
    - where subset (heuristic)
    """
    ok, reasons = basic_static_safety_checks(user_sql)
    if not ok:
        return False, reasons

    u_tables = extract_tables(user_sql)
    a_tables = extract_tables(auth_sql)

    if not u_tables:
        reasons.append("Could not extract table(s) from user query.")
        return False, reasons

    # Only allow tables that are in allowed_tables AND also in the authorized query tables
    if not u_tables.issubset(allowed_tables):
        reasons.append(f"User tables {u_tables} are not all in allowed tables {allowed_tables}.")
        return False, reasons

    if not u_tables.issubset(a_tables):
        reasons.append(f"User tables {u_tables} must be a subset of authorized tables {a_tables}.")
        return False, reasons

    u_cols = extract_columns(user_sql)
    a_cols = extract_columns(auth_sql)

    # If user selects *, then authorized must also allow *.
    if "*" in u_cols and "*" not in a_cols:
        reasons.append("User selects '*' but authorized query does not allow '*'")
        return False, reasons

    # If authorized selects *, allow any columns; otherwise require subset
    if "*" not in a_cols and "*" not in u_cols:
        if not u_cols.issubset(a_cols):
            reasons.append(f"User columns {u_cols} must be subset of authorized columns {a_cols}.")
            return False, reasons

    # Where clause subset (naive)
    if not implies_subset(where_clause(user_sql), where_clause(auth_sql)):
        reasons.append("WHERE clause of user query is not a subset of authorized query (heuristic).")
        return False, reasons

    return True, ["Passed static containment checks."]
