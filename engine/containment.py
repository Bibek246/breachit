from __future__ import annotations
from typing import Dict, List, Tuple, Any, Set
import re

SAFE_SELECT_RE = re.compile(r"^\s*select\s", re.IGNORECASE | re.DOTALL)

# Symbolic tokens to block anywhere (substring is fine)
FORBIDDEN_TOKENS = [
    ";", "--", "/*", "*/"
]

# SQL keywords to block only as standalone words (won't match inside identifiers like `created_at`)
FORBIDDEN_KEYWORDS = [
    "drop", "insert", "update", "delete", "alter", "create", "attach", "pragma", "vacuum",
    "grant", "revoke", "truncate"
]

UNION_RE = re.compile(r"\bunion\b", re.IGNORECASE)
JOIN_RE = re.compile(r"\bjoin\b", re.IGNORECASE)

IDENT_RE = r"[A-Za-z_][A-Za-z0-9_]*"
TABLE_EXTRACT_RE = re.compile(r"from\s+(" + IDENT_RE + r")(?:\s+\w+)?", re.IGNORECASE)
TABLES_EXTRACT_RE = re.compile(
    r"from\s+(" + IDENT_RE + r")(?:\s+\w+)?(?:\s*,\s*(" + IDENT_RE + r")(?:\s+\w+)?)?",
    re.IGNORECASE
)
SELECT_COLS_RE = re.compile(r"select\s+(.*?)\s+from", re.IGNORECASE | re.DOTALL)

def tokenize_identifiers(expr: str) -> Set[str]:
    return set(re.findall(IDENT_RE, expr))

def basic_static_safety_checks(sql: str) -> Tuple[bool, List[str]]:
    """
    Basic static checks to ensure:
    - Single SELECT only
    - No dangerous tokens (symbols)
    - No dangerous DDL/DML keywords (word-boundary match)
    - No UNIONs
    """
    reasons: List[str] = []
    s = sql.strip()
    if not SAFE_SELECT_RE.match(s):
        reasons.append("Only single SELECT statements are allowed.")
    lowered = s.lower()

    # Symbol tokens: substring detection is fine
    for tok in FORBIDDEN_TOKENS:
        if tok in lowered:
            reasons.append(f"Forbidden token detected: {tok}")

    # Keywords: block only on word boundaries
    for kw in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{re.escape(kw)}\b", lowered):
            reasons.append(f"Forbidden keyword detected: {kw}")

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
    parts = [p.strip() for p in cols.split(",")]
    norm = set()
    for p in parts:
        norm.add(p.lower())
    return norm

def where_clause(sql: str) -> str:
    m = re.search(r"\bwhere\b(.*?)(?:\bgroup\b|\border\b|$)", sql, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else ""

def normalized_space(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()

def implies_subset(user_where: str, auth_where: str) -> bool:
    """
    Heuristic subset check:
    - Treat authorized named parameters (e.g., :user_id) as WILDCARD
    - Normalize user literals (numbers/strings) to WILDCARD
    - Then require all auth tokens to appear in user tokens
    NOTE: still a toy heuristic for the prototype.
    """
    def normalize_clause(s: str) -> str:
        s = normalized_space(s)
        return s

    u = normalize_clause(user_where)
    a = normalize_clause(auth_where)

    # If the authorized WHERE is empty, user's must also be empty to be a subset
    if not a:
        return u == ""

    import re
    # Replace named params in authorized clause with a placeholder
    a_norm = re.sub(r":\w+", "WILDCARD", a)

    # Replace user literals (numbers and quoted strings) with the same placeholder
    u_norm = re.sub(r"\b\d+(\.\d+)?\b", "WILDCARD", u)             # numbers
    u_norm = re.sub(r"'[^']*'", "WILDCARD", u_norm)                # 'strings'
    u_norm = re.sub(r"\"[^\"]*\"", "WILDCARD", u_norm)             # "strings"

    # Tokenize on whitespace; require auth tokens to be subset of user tokens
    auth_tokens = set(a_norm.split())
    user_tokens = set(u_norm.split())

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

    if not u_tables.issubset(allowed_tables):
        reasons.append(f"User tables {u_tables} are not all in allowed tables {allowed_tables}.")
        return False, reasons

    if not u_tables.issubset(a_tables):
        reasons.append(f"User tables {u_tables} must be a subset of authorized tables {a_tables}.")
        return False, reasons

    u_cols = extract_columns(user_sql)
    a_cols = extract_columns(auth_sql)

    if "*" in u_cols and "*" not in a_cols:
        reasons.append("User selects '*' but authorized query does not allow '*'")
        return False, reasons

    if "*" not in a_cols and "*" not in u_cols:
        if not u_cols.issubset(a_cols):
            reasons.append(f"User columns {u_cols} must be subset of authorized columns {a_cols}.")
            return False, reasons

    if not implies_subset(where_clause(user_sql), where_clause(auth_sql)):
        reasons.append("WHERE clause of user query is not a subset of authorized query (heuristic).")
        return False, reasons

    return True, ["Passed static containment checks."]
