import os
import sqlite3
from flask import Flask, request, jsonify

app = Flask(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "data.db")
GATEWAY_KEY = os.environ.get("GATEWAY_KEY", "dev-gateway-secret-123")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def require_gateway_key():
    """校验网关凭据。不通过 -> 直接拒绝。"""
    key = request.headers.get("X-Gateway-Key", "")
    if not key or key != GATEWAY_KEY:
        return jsonify({"error": "unauthorized: gateway key required"}), 401
    return None


@app.route("/internal/score", methods=["POST"])
def internal_get_score():
    """查询单个学生某课程成绩。返回记录级完整字段。"""
    err = require_gateway_key()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    student_id = body.get("student_id")
    course = body.get("course")

    if not student_id or not course:
        return jsonify({"error": "missing student_id or course"}), 400

    conn = get_db()
    row = conn.execute(
        """
        SELECT s.student_id, s.name, s.class, s.phone, s.address,
               sc.course, sc.score
        FROM students s
        JOIN scores sc ON s.student_id = sc.student_id
        WHERE s.student_id = ? AND sc.course = ?
        """,
        (student_id, course),
    ).fetchone()
    conn.close()

    if row is None:
        return jsonify({"error": "not found"}), 404

    return jsonify(dict(row)), 200


@app.route("/internal/class_scores", methods=["POST"])
def internal_get_class_scores():
    """查询某班级某课程成绩列表。返回记录级完整字段。"""
    err = require_gateway_key()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    class_name = body.get("class")
    course = body.get("course")

    if not class_name or not course:
        return jsonify({"error": "missing class or course"}), 400

    conn = get_db()
    rows = conn.execute(
        """
        SELECT s.student_id, s.name, s.class, s.phone, s.address,
               sc.course, sc.score
        FROM students s
        JOIN scores sc ON s.student_id = sc.student_id
        WHERE s.class = ? AND sc.course = ?
        ORDER BY s.student_id
        """,
        (class_name, course),
    ).fetchall()
    conn.close()

    return jsonify([dict(r) for r in rows]), 200

@app.route("/internal/check_assistant_class", methods=["POST"])
def internal_check_assistant_class():
    err = require_gateway_key()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    assistant_id = body.get("assistant_id")
    class_name = body.get("class")

    if not assistant_id or not class_name:
        return jsonify({"error": "missing params"}), 400

    conn = get_db()
    row = conn.execute(
        "SELECT 1 FROM assistant_classes WHERE assistant_id = ? AND class = ?",
        (assistant_id, class_name),
    ).fetchone()
    conn.close()

    return jsonify({"allowed": row is not None}), 200
@app.route("/internal/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    # 数据接口只在内网/本机用，端口 5002
    app.run(host="127.0.0.1", port=5002, debug=True)