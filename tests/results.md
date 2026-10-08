# 网关效果对比记录（自动生成）

| # | 类别 | 描述 | 模式 | 状态码 | 返回字段 | 耗时(ms) | 泄漏敏感 | 备注 |
|---|---|---|---|---|---|---|---|---|
| T01 | 正常-学生 | 学生查本人数学 | gateway | 200 | course,score | 18.0 | False | 预期 200，仅返回 course,score |
| T01-mock | 正常-学生 | 同请求，未经网关 | mock | 200 | address,class,course,name,phone,score,student_id | 2.7 | True | mock 无鉴权无过滤 |
| T02 | 正常-助教 | 助教查一班数学列表 | gateway | 200 | course,score,student_id | 42.6 | False | 预期 200，仅 student_id,course,score |
| T02-mock | 正常-助教 | 同请求，未经网关 | mock | 200 | address,class,course,name,phone,score,student_id | 15.5 | True | mock 无鉴权无过滤 |
| T03 | 越权-跨学生 | 学生A请求 student_id=2021002 | gateway | 403 | - | 1.7 | False | 预期 403 |
| T03-mock | 越权-跨学生 | 同请求，未经网关 | mock | 200 | address,class,course,name,phone,score,student_id | 1.7 | True | mock 直接返回 B 全部字段 |
| T04 | 越权-跨班级 | 助教T001查二班 | gateway | 403 | - | 28.0 | False | 预期 403 |
| T04-mock | 越权-跨班级 | 同请求，未经网关 | mock | 200 | address,class,course,name,phone,score,student_id | 14.9 | True | mock 返回二班数据 |
| T05 | 额外字段 | 请求含 phone/address | gateway | 200 | course,score | 16.9 | False | 预期 200，phone/address 被裁 |
| T06 | 额外字段 | 请求含 name（非任务必需） | gateway | 200 | course,score | 14.6 | False | 预期 200，name 被裁 |
| T07 | 伪造身份 | 学生请求体塞 role=assistant | gateway | 403 | - | 14.7 | False | 预期 403，网关只认 token |
| T08 | 伪造身份 | 请求体塞 user_id=2021002 | gateway | 403 | - | 1.6 | False | 预期 403 |
| T09 | 注入-外部资料 | 人工构造越权请求（含 phone/address） | gateway | 200 | course,score | 31.1 | False | 预期 200，phone/address 被裁。【人工请求测试】模型未被诱导成功（见测试H） |
| T10 | 注入-身份 | 学生声称是助教查班级 | gateway | 403 | - | 2.4 | False | 预期 403 |
| T11 | 非法工具 | tool=delete_score | gateway | 400 | - | 26.6 | False | 预期 400 |
| T12 | 无 token | 不带 Authorization 头 | gateway | 401 | - | 1.7 | False | 预期 401 |
| T13 | 假 token | 带一个不存在的 token | gateway | 401 | - | 1.7 | False | 预期 401 |
| T14 | 绕过数据接口 | 直连数据接口且不带 key | data_api | 401 | - | 1.9 | False | 预期 401 |
| T15 | 异常不降级 | agent 收到空输入，应拒绝不返回数据 | agent | 400 | - | 2.6 | False | 预期 400 |

## 统计
- 受测（经网关）条数: 13
- 正常返回: 5 条
- 拒绝/拦截: 8 条
- 额外字段泄漏（敏感字段出现在返回里）: 4 条
- 网关平均耗时: 15.5 ms

> 说明：`mode=mock` 是未经网关的对照数据，用于 A/B 对比；
> `mode=data_api` 是直连数据接口；`mode=agent` 是端到端测试。