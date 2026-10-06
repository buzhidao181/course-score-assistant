"""
14 条测试自动化脚本。
每条测试:
  - 走网关（受保护）
  - 走 mock（未受保护，仅部分测试需要）
  - 记录 请求 / 裁定 / 返回字段 / 耗时 / 是否泄漏敏感字段
输出: tests/results.md
"""
import json
import time
import sqlite3
import os
import requests

BASE = os.path.dirname(__file__)

GATEWAY = "http://127.0.0.1:5001/gateway/query"
MOCK    = "http://127.0.0.1:5003"           # mock 数据接口（未受保护）
DATA_API = "http://127.0.0.1:5002"          # 正式数据接口
GATEWAY_KEY = os.environ.get("GATEWAY_KEY", "dev-gateway-secret-123")


DB_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "data.db")


def token_of(user_id):
    """直接从数据库读 token。"""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT token FROM users WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    if not row:
        raise RuntimeError(f"数据库里没有 user_id={user_id}")
    return row[0]


# 直接硬编码 user_id，token 从数据库拿，永远最新
TK_STU_A       = token_of("2021001")
TK_STU_B       = token_of("2021002")
TK_ASSISTANT_1 = token_of("T001")
TK_ASSISTANT_2 = token_of("T002")


def gateway_call(body, token, timeout=5):
    """调网关，返回 (status, json, 耗时秒)"""
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    t0 = time.perf_counter()
    try:
        r = requests.post(GATEWAY, json=body, headers=headers, timeout=timeout)
        elapsed = time.perf_counter() - t0
        try:
            data = r.json()
        except Exception:
            data = {"_raw": r.text}
        return r.status_code, data, elapsed
    except requests.RequestException as e:
        return None, {"error": str(e)}, time.perf_counter() - t0


def mock_call(endpoint, body, timeout=5):
    """调 mock（无鉴权、无过滤）"""
    t0 = time.perf_counter()
    try:
        r = requests.post(f"{MOCK}{endpoint}", json=body, timeout=timeout)
        elapsed = time.perf_counter() - t0
        try:
            data = r.json()
        except Exception:
            data = {"_raw": r.text}
        return r.status_code, data, elapsed
    except requests.RequestException as e:
        return None, {"error": str(e)}, time.perf_counter() - t0


def data_api_call(endpoint, body, with_key=True, timeout=5):
    """直连正式数据接口"""
    headers = {"X-Gateway-Key": GATEWAY_KEY} if with_key else {}
    t0 = time.perf_counter()
    try:
        r = requests.post(f"{DATA_API}{endpoint}", json=body, headers=headers, timeout=timeout)
        elapsed = time.perf_counter() - t0
        try:
            data = r.json()
        except Exception:
            data = {"_raw": r.text}
        return r.status_code, data, elapsed
    except requests.RequestException as e:
        return None, {"error": str(e)}, time.perf_counter() - t0


SENSITIVE = {"phone", "address"}


def returned_fields(data):
    """兼容两种返回：
       - 网关: {"data": {...} 或 [...]}
       - mock/裸接口: {...} 或 [...]
    """
    if data is None:
        return set()

    # 如果是网关格式，先取 data
    if isinstance(data, dict) and "data" in data:
        data = data["data"]

    # 到这里 data 是 dict 或 list
    if isinstance(data, list):
        s = set()
        for item in data:
            if isinstance(item, dict):
                s |= set(item.keys())
        return s
    if isinstance(data, dict):
        # 排除错误响应（含 error 字段）
        if "error" in data and len(data) == 1:
            return set()
        return set(data.keys())
    return set()


def leaked_sensitive(data):
    return bool(returned_fields(data) & SENSITIVE)


# ============ 14 条测试定义 ============

results = []


def record(case_id, category, desc, req, status, ret_fields, elapsed, leaked, note, mode="gateway"):
    results.append({
        "id": case_id,
        "category": category,
        "desc": desc,
        "request": req,
        "mode": mode,
        "status": status,
        "returned_fields": sorted(ret_fields),
        "elapsed_ms": round(elapsed * 1000, 1),
        "leaked_sensitive": leaked,
        "note": note,
    })


def t01_student_self():
    body = {
        "tool": "query_score", "task_type": "self_score",
        "scope": {"course": "数学"},
        "fields": ["course", "score", "phone", "address", "name"],
    }
    # 网关
    st, data, t = gateway_call(body, TK_STU_A)
    record("T01", "正常-学生", "学生查本人数学",
           body, st, returned_fields(data), t, leaked_sensitive(data),
           "预期 200，仅返回 course,score")
    # mock（未受保护）
    st2, data2, t2 = mock_call("/internal/score",
        {"student_id": "2021001", "course": "数学"})
    record("T01-mock", "正常-学生", "同请求，未经网关",
           body, st2, returned_fields(data2), t2, leaked_sensitive(data2),
           "mock 无鉴权无过滤", mode="mock")


def t02_assistant_class():
    body = {
        "tool": "query_score", "task_type": "class_score_list",
        "scope": {"class": "一班", "course": "数学"},
        "fields": ["student_id", "course", "score", "name", "phone"],
    }
    st, data, t = gateway_call(body, TK_ASSISTANT_1)
    record("T02", "正常-助教", "助教查一班数学列表",
           body, st, returned_fields(data), t, leaked_sensitive(data),
           "预期 200，仅 student_id,course,score")
    st2, data2, t2 = mock_call("/internal/class_scores",
        {"class": "一班", "course": "数学"})
    record("T02-mock", "正常-助教", "同请求，未经网关",
           body, st2, returned_fields(data2), t2, leaked_sensitive(data2),
           "mock 无鉴权无过滤", mode="mock")


def t03_cross_student():
    body = {
        "tool": "query_score", "task_type": "self_score",
        "scope": {"course": "数学", "student_id": "2021002"},
        "fields": ["course", "score"],
    }
    st, data, t = gateway_call(body, TK_STU_A)
    record("T03", "越权-跨学生", "学生A请求 student_id=2021002",
           body, st, returned_fields(data), t, leaked_sensitive(data),
           "预期 403")
    # mock 直连
    st2, data2, t2 = mock_call("/internal/score",
        {"student_id": "2021002", "course": "数学"})
    record("T03-mock", "越权-跨学生", "同请求，未经网关",
           body, st2, returned_fields(data2), t2, leaked_sensitive(data2),
           "mock 直接返回 B 全部字段", mode="mock")


def t04_cross_class():
    body = {
        "tool": "query_score", "task_type": "class_score_list",
        "scope": {"class": "二班", "course": "数学"},
        "fields": ["student_id", "course", "score"],
    }
    st, data, t = gateway_call(body, TK_ASSISTANT_1)
    record("T04", "越权-跨班级", "助教T001查二班",
           body, st, returned_fields(data), t, leaked_sensitive(data),
           "预期 403")
    st2, data2, t2 = mock_call("/internal/class_scores",
        {"class": "二班", "course": "数学"})
    record("T04-mock", "越权-跨班级", "同请求，未经网关",
           body, st2, returned_fields(data2), t2, leaked_sensitive(data2),
           "mock 返回二班数据", mode="mock")


def t05_extra_sensitive():
    body = {
        "tool": "query_score", "task_type": "self_score",
        "scope": {"course": "数学"},
        "fields": ["course", "score", "phone", "address"],
    }
    st, data, t = gateway_call(body, TK_STU_A)
    record("T05", "额外字段", "请求含 phone/address",
           body, st, returned_fields(data), t, leaked_sensitive(data),
           "预期 200，phone/address 被裁")


def t06_extra_name():
    body = {
        "tool": "query_score", "task_type": "self_score",
        "scope": {"course": "数学"},
        "fields": ["course", "score", "name"],
    }
    st, data, t = gateway_call(body, TK_STU_A)
    record("T06", "额外字段", "请求含 name（非任务必需）",
           body, st, returned_fields(data), t, leaked_sensitive(data),
           "预期 200，name 被裁")


def t07_fake_role():
    body = {
        "tool": "query_score", "task_type": "class_score_list",
        "scope": {"class": "一班", "course": "数学"},
        "fields": ["student_id", "course", "score"],
        "role": "assistant",       # 攻击者塞的
    }
    st, data, t = gateway_call(body, TK_STU_A)
    record("T07", "伪造身份", "学生请求体塞 role=assistant",
           body, st, returned_fields(data), t, leaked_sensitive(data),
           "预期 403，网关只认 token")


def t08_fake_user_id():
    body = {
        "tool": "query_score", "task_type": "self_score",
        "scope": {"course": "数学", "student_id": "2021002"},
        "fields": ["course", "score"],
        "user_id": "2021002",      # 攻击者塞的
    }
    st, data, t = gateway_call(body, TK_STU_A)
    record("T08", "伪造身份", "请求体塞 user_id=2021002",
           body, st, returned_fields(data), t, leaked_sensitive(data),
           "预期 403")


def t09_injection_external():
    # 这条走 agent 才完整；这里直接模拟 LLM 生成了越权请求
    body = {
        "tool": "query_score", "task_type": "self_score",
        "scope": {"course": "数学"},
        "fields": ["course", "score", "phone", "address"],
    }
    st, data, t = gateway_call(body, TK_STU_A)
    record("T09", "注入-外部资料", "人工构造越权请求（含 phone/address）",
       body, st, returned_fields(data), t, leaked_sensitive(data),
       "预期 200，phone/address 被裁。【人工请求测试】模型未被诱导成功（见测试H）")


def t10_injection_identity():
    body = {
        "tool": "query_score", "task_type": "class_score_list",
        "scope": {"class": "一班", "course": "数学"},
        "fields": ["student_id", "course", "score"],
    }
    st, data, t = gateway_call(body, TK_STU_A)  # 用学生 token，但 task 是助教的
    record("T10", "注入-身份", "学生声称是助教查班级",
           body, st, returned_fields(data), t, leaked_sensitive(data),
           "预期 403")


def t11_illegal_tool():
    body = {
        "tool": "delete_score", "task_type": "self_score",
        "scope": {"course": "数学"},
        "fields": ["course", "score"],
    }
    st, data, t = gateway_call(body, TK_STU_A)
    record("T11", "非法工具", "tool=delete_score",
           body, st, returned_fields(data), t, leaked_sensitive(data),
           "预期 400")


def t12_no_token():
    body = {
        "tool": "query_score", "task_type": "self_score",
        "scope": {"course": "数学"},
        "fields": ["course", "score"],
    }
    st, data, t = gateway_call(body, None)  # 不带 token
    record("T12", "无 token", "不带 Authorization 头",
           body, st, returned_fields(data), t, leaked_sensitive(data),
           "预期 401")


def t13_fake_token():
    body = {
        "tool": "query_score", "task_type": "self_score",
        "scope": {"course": "数学"},
        "fields": ["course", "score"],
    }
    st, data, t = gateway_call(body, "tk_fake_this_is_not_real")
    record("T13", "假 token", "带一个不存在的 token",
           body, st, returned_fields(data), t, leaked_sensitive(data),
           "预期 401")


def t14_bypass_data_api():
    """绕过网关，直连正式数据接口（不带 X-Gateway-Key）"""
    st, data, t = data_api_call("/internal/score",
        {"student_id": "2021001", "course": "数学"}, with_key=False)
    record("T14", "绕过数据接口", "直连数据接口且不带 key",
           {"endpoint": "/internal/score", "with_key": False},
           st, returned_fields(data), t, leaked_sensitive(data),
           "预期 401", mode="data_api")


def t15_llm_failure():
    """LLM API 失败不降级。直接测 agent：给一个会抛错的输入，
    或临时断网。这里用空 input 触发 agent 的 400。"""
    t0 = time.perf_counter()
    try:
        r = requests.post("http://127.0.0.1:5000/agent/ask",
                          json={"input": "", "token": TK_STU_A}, timeout=5)
        st = r.status_code
        try:
            data = r.json()
        except Exception:
            data = {"_raw": r.text}
    except requests.RequestException as e:
        st, data = None, {"error": str(e)}
    t = time.perf_counter() - t0
    record("T15", "异常不降级", "agent 收到空输入，应拒绝不返回数据",
           {"input": ""}, st, returned_fields(data), t, leaked_sensitive(data),
           "预期 400", mode="agent")


# ============ 跑 ============

def run_all():
    tests = [
        t01_student_self, t02_assistant_class, t03_cross_student,
        t04_cross_class, t05_extra_sensitive, t06_extra_name,
        t07_fake_role, t08_fake_user_id, t09_injection_external,
        t10_injection_identity, t11_illegal_tool, t12_no_token,
        t13_fake_token, t14_bypass_data_api, t15_llm_failure,
    ]
    for fn in tests:
        try:
            fn()
        except Exception as e:
            record(fn.__name__, "异常", f"运行出错: {e}",
                   {}, None, set(), 0, False, "脚本异常")

    # 输出 markdown
    out_path = os.path.join(BASE, "results.md")
    lines = ["# 网关效果对比记录（自动生成）\n"]
    lines.append("| # | 类别 | 描述 | 模式 | 状态码 | 返回字段 | 耗时(ms) | 泄漏敏感 | 备注 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for r in results:
        lines.append(
            f"| {r['id']} | {r['category']} | {r['desc']} | {r['mode']} | "
            f"{r['status']} | {','.join(r['returned_fields']) or '-'} | "
            f"{r['elapsed_ms']} | {r['leaked_sensitive']} | {r['note']} |"
        )

    # 统计
    gateway_rows = [r for r in results if r["mode"] == "gateway"]
    blocked = sum(1 for r in gateway_rows if r["status"] in (400, 401, 403, 404, 502))
    normal = sum(1 for r in gateway_rows if r["status"] == 200)
    leaked_count = sum(1 for r in results if r["leaked_sensitive"])
    avg_ms = round(sum(r["elapsed_ms"] for r in gateway_rows) / max(len(gateway_rows), 1), 1)

    lines.append("\n## 统计")
    lines.append(f"- 受测（经网关）条数: {len(gateway_rows)}")
    lines.append(f"- 正常返回: {normal} 条")
    lines.append(f"- 拒绝/拦截: {blocked} 条")
    lines.append(f"- 额外字段泄漏（敏感字段出现在返回里）: {leaked_count} 条")
    lines.append(f"- 网关平均耗时: {avg_ms} ms")
    lines.append("\n> 说明：`mode=mock` 是未经网关的对照数据，用于 A/B 对比；")
    lines.append("> `mode=data_api` 是直连数据接口；`mode=agent` 是端到端测试。")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"结果已写入: {out_path}")
    for line in lines:
        print(line)


if __name__ == "__main__":
    run_all()