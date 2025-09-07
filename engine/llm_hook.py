from __future__ import annotations
from typing import Optional

def llm_containment_hint(user_sql: str, authorized_sql: str, context: str = "") -> Optional[bool]:
    """
    Stub: return None (unknown) or a boolean hint whether user_sql is contained by authorized_sql.
    Replace this with a real model call if desired.
    """
    # For now, don't bias; return None to indicate "no extra info".
    return None
