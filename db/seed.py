import sqlite3
import secrets
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")

# 清掉旧库，重新生成
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# 建表
with open(os.path.join(os.path.dirname(__file__), "schema.sql"), encoding="utf-8") as f:
    cur.executescript(f.read())

# ------- 合成数据 -------
students = [
    # student_id, name, class, phone, address
    ("2021001", "张三", "一班", "13800000001", "某市某路1号"),
    ("2021002", "李四", "一班", "13800000002", "某市某路2号"),
    ("2021003", "王五", "一班", "13800000003", "某市某路3号"),
    ("2022001", "赵六", "二班", "13800000004", "某市某路4号"),
    ("2022002", "钱七", "二班", "13800000005", "某市某路5号"),
    ("2022003", "孙八", "二班", "13800000006", "某市某路6号"),
]

scores = [
    ("2021001", "数学", 88), ("2021001", "英语", 92),
    ("2021002", "数学", 75), ("2021002", "英语", 80),
    ("2021003", "数学", 60), ("2021003", "英语", 70),
    ("2022001", "数学", 95), ("2022001", "英语", 85),
    ("2022002", "数学", 55), ("2022002", "英语", 65),
    ("2022003", "数学", 78), ("2022003", "英语", 88),
]

# 助教：T001 负责一班，T002 负责二班
assistants = [
    ("T001", "一班"),
    ("T002", "二班"),
]

# ------- 写入 -------
cur.executemany("INSERT INTO students VALUES (?,?,?,?,?)", students)
cur.executemany("INSERT INTO scores VALUES (?,?,?)", scores)
cur.executemany("INSERT INTO assistant_classes VALUES (?,?)", assistants)

# ------- 生成 token 映射 -------
tokens = {}  # 打印用

# 学生 token
for sid, name, cls, *_ in students:
    tok = "tk_" + secrets.token_urlsafe(24)
    cur.execute("INSERT INTO users VALUES (?,?,?)", (tok, sid, "student"))
    tokens[f"student {sid} ({name})"] = tok

# 助教 token
for aid, cls in assistants:
    tok = "tk_" + secrets.token_urlsafe(24)
    cur.execute("INSERT INTO users VALUES (?,?,?)", (tok, aid, "assistant"))
    tokens[f"assistant {aid} (负责{cls})"] = tok

conn.commit()
conn.close()

print("数据库已生成:", DB_PATH)
print("\n===== Token 映射（测试要用，保存好）=====")
for k, v in tokens.items():
    print(f"{k:40s} {v}")