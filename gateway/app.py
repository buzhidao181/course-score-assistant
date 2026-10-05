import os
import requests
from flask import Flask, request, jsonify

from policy import (
    ALLOWED_TOOLS, ROLE_TASKS, TASK_FIELDS,
    FORBIDDEN_FIELDS, allowed_final_fields,
)
from identity import resolve_identity

app = Flask(__name__)

DATA_API = "http://127.0.0.1:5002"
GATEWAY_KEY = os.environ.get("GATEWAY_KEY", "dev-gateway-secret-123")


def reject(code, msg):
    return jsonify({"error": msg}), code


@app.route("/gateway/query", methods=["POST"])
def gateway_query():
    # ---- 1. 解析身份（只认 token）----
    identity, err = resolve_identity()
    if identity is None:
        return reject(401, f"auth failed: {err}")
    user_id, role = identity

    body = request.get_json(silent=True) or {}

    # ---- 2. 工具白名单 ----
    tool = body.get("tool")
    if tool not in ALLOWED_TOOLS:
        return reject(400, f"tool not allowed: {tool}")

    # ---- 3. task_type 与角色匹配 ----
    task_type = body.get("task_type")
    if task_type not in ROLE_TASKS.get(role, set()):
        return reject(403, f"role {role} cannot use task {task_type}")

    # ---- 4. scope 范围校验 ----
    scope = body.get("scope") or {}
    course = scope.get("course")
    if not course:
        return reject(400, "missing course in scope")

    if task_type == "self_score":
        # 学生：强制 student_id = 本人；忽略/拒绝请求体里任何 student_id
        req_sid = scope.get("student_id")
        if req_sid and req_sid != user_id:
            return reject(403, "cannot query other students")
        effective_student_id = user_id
        data_call = {"student_id": effective_student_id, "course": course}

    elif task_type == "class_score_list":
        # 助教：班级必须在负责班级里
        class_name = scope.get("class")
        if not class_name:
            return reject(400, "missing class in scope")

        conn_resp = requests.post(
            f"{DATA_API}/internal/check_assistant_class",
            json={"assistant_id": user_id, "class": class_name},
            headers={"X-Gateway-Key": GATEWAY_KEY},
            timeout=3,
        )
        if conn_resp.status_code != 200 or not conn_resp.json().get("allowed"):
            return reject(403, "class not in your responsibility")
        data_call = {"class": class_name, "course": course}
    else:
        return reject(400, "unknown task_type")

    # ---- 5. 计算最终字段（三重交集）----
    requested_fields = body.get("fields") or []
    final_fields = allowed_final_fields(role, task_type, requested_fields)

    # 如果交集为空 → 拒绝（不降级为返回全字段）
    if not final_fields:
        return reject(400, "no permitted fields to return")

    # ---- 6. 调数据接口 ----
    if task_type == "self_score":
        url = f"{DATA_API}/internal/score"
    else:
        url = f"{DATA_API}/internal/class_scores"

    try:
        resp = requests.post(
            url, json=data_call,
            headers={"X-Gateway-Key": GATEWAY_KEY},
            timeout=3,
        )
    except requests.RequestException as e:
        # 任何 API 失败 → 拒绝，不降级
        return reject(502, f"data api failure: {e}")

    if resp.status_code == 404:
        return reject(404, "record not found")
    if resp.status_code != 200:
        return reject(502, f"data api error: {resp.status_code}")

    raw = resp.json()

    # ---- 7. 返回前再裁剪一次 ----
    def trim(record):
        return {k: record[k] for k in final_fields if k in record}

    if isinstance(raw, list):
        result = [trim(r) for r in raw]
    else:
        result = trim(raw)

    return jsonify({
        "identity": {"user_id": user_id, "role": role},
        "task_type": task_type,
        "returned_fields": sorted(final_fields),
        "data": result,
    }), 200


@app.route("/gateway/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)