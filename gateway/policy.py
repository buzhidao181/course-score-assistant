# ============ 策略表：硬编码，不可被请求体/LLM 改变 ============

# 允许调用的工具白名单
ALLOWED_TOOLS = {"query_score"}

# 任务类型 -> 该任务"必需字段"
TASK_FIELDS = {
    "self_score":       {"course", "score"},
    "class_score_list": {"student_id", "course", "score"},
}

# 角色 -> 允许访问的字段（记录级权限）
ROLE_ALLOWED_FIELDS = {
    "student":   {"student_id", "name", "course", "score"},
    "assistant": {"student_id", "name", "course", "score"},
}

# 永久禁止返回的字段（任何角色、任何任务）
FORBIDDEN_FIELDS = {"phone", "address"}

# 角色 -> 允许的 task_type
ROLE_TASKS = {
    "student":   {"self_score"},
    "assistant": {"class_score_list"},
}


def allowed_final_fields(role, task_type, requested_fields):
    """
    三重交集：
      请求字段 ∩ 角色允许字段 ∩ 任务所需字段 − 禁止字段
    """
    requested = set(requested_fields or [])
    role_ok = ROLE_ALLOWED_FIELDS.get(role, set())
    task_ok = TASK_FIELDS.get(task_type, set())

    final = (requested & role_ok & task_ok) - FORBIDDEN_FIELDS
    return final