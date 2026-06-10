"""
Step 1: 拉春10 标单 (issue=844) 的反馈电话样本
- type25(反馈关单) / type69(完习回访) 全量
- 同期所有有 call_text_url 的成功外呼电话
- 后续在 step2 做匹配
"""
import json
from pathlib import Path

BASE = Path(__file__).parent
RAW = BASE / "raw"
RAW.mkdir(exist_ok=True)

# 由 LLM 在交互里调用 dbpaas MCP 拉取后落到 raw/
# 这里只做接收脚本说明
print("This file documents the SQL queries we'll send via dbpaas MCP.")
print("")
print("Q1: 反馈关单/完习回访记录 (type25, type69)")
print("""
SELECT user_id, tutor_ldap, communication_type, status,
       UNIX_TIMESTAMP(dbctime) AS comm_ts,
       DATE_FORMAT(dbctime, '%Y-%m-%d %H:%i:%s') AS comm_dt
FROM communication_record
WHERE issue_id = 844
  AND communication_type IN (25, 69)
ORDER BY user_id, dbctime
""")

print("Q2: issue=844 期间所有可用电话（呼出、成功、有转写、>=60s）")
print("""
SELECT ytk_user_id, tutor_ldap, call_id, start_time, start_time_mills, duration, call_text_url
FROM tutor_call_record
WHERE issue_id = 844
  AND call_type = 1
  AND status = 1
  AND duration >= 60
  AND call_text_url IS NOT NULL
  AND start_time >= 1745164800000  -- 2026-04-21 00:00 (服务前几天)
ORDER BY ytk_user_id, start_time
""")
