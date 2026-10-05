-- 学生表
CREATE TABLE students (
  student_id TEXT PRIMARY KEY,
  name       TEXT NOT NULL,
  class      TEXT NOT NULL,
  phone      TEXT,
  address    TEXT
);

-- 成绩表
CREATE TABLE scores (
  student_id TEXT NOT NULL,
  course     TEXT NOT NULL,
  score      INTEGER NOT NULL
);

-- 身份映射表（信任根：token -> 身份）
CREATE TABLE users (
  token   TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  role    TEXT NOT NULL CHECK (role IN ('student','assistant'))
);

-- 助教负责班级表
CREATE TABLE assistant_classes (
  assistant_id TEXT NOT NULL,
  class        TEXT NOT NULL
);