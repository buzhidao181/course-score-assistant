import os
import sqlite3
from flask import request

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "data.db")


def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def resolve_identity():
    """
    从 Authorization: Bearer <token> 解析身份。
    返回 (user_id, role) 或 (None, None)（表示鉴权失败）。
    绝不读取请求体里的 role/user_id。
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None, "missing token"

    token = auth[len("Bearer "):].strip()
    if not token:
        return None, "empty token"

    conn = _db()
    row = conn.execute(
        "SELECT user_id, role FROM users WHERE token = ?", (token,)
    ).fetchone()
    conn.close()

    if row is None:
        return None, "unknown token"

    return (row["user_id"], row["role"]), None