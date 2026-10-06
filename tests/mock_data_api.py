"""
测试专用 mock 服务：模拟"未启用网关"的情况。
直接返回全字段，不做任何权限和字段过滤。
仅用于 A/B 对比，不属于生产代码。
"""
import os
import sqlite3
from flask import Flask, request, jsonify

app = Flask(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "data.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/internal/score", methods=["POST"])
def score():
    body = request.get_json(silent=True) or {}
    sid = body.get("student_id")
    course = body.get("course")
    conn = get_db()
    row = conn.execute(
        """
        SELECT s.student_id, s.name, s.class, s.phone, s.address,
               sc.course, sc.score
        FROM students s JOIN scores sc ON s.student_id = sc.student_id
        WHERE s.student_id = ? AND sc.course = ?
        """,
        (sid, course),
    ).fetchone()
    conn.close()
    if row is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(dict(row)), 200


@app.route("/internal/class_scores", methods=["POST"])
def class_scores():
    body = request.get_json(silent=True) or {}
    cls = body.get("class")
    course = body.get("course")
    conn = get_db()
    rows = conn.execute(
        """
        SELECT s.student_id, s.name, s.class, s.phone, s.address,
               sc.course, sc.score
        FROM students s JOIN scores sc ON s.student_id = sc.student_id
        WHERE s.class = ? AND sc.course = ?
        ORDER BY s.student_id
        """,
        (cls, course),
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows]), 200


if __name__ == "__main__":
    # 端口 5003，与正式数据接口(5002)隔离
    app.run(host="127.0.0.1", port=5003, debug=False)