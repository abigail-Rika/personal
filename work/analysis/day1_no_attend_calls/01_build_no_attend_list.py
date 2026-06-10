"""
基于已拉取的底盘 + Day1 学习状态，算出 Day1 无记录用户名单
口径：直投春10 A+B (issue 846/847) → user_day_study_status 中 day_no=1 完全无记录
"""
import json
import csv
from pathlib import Path

BASE = Path(__file__).parent
TOOLS = Path("/Users/jiwenyue/.cursor/projects/Users-jiwenyue-Abigial/agent-tools")

# 1. 底盘
with open(TOOLS / "0931e372-5953-4be8-9f37-127feb206cf5.txt") as f:
    roster_data = json.load(f)
roster_rows = roster_data["data"]["rows"]
# columns: user_id, tutor_ldap, issue_id, dbctime
roster = [
    {"user_id": r[0], "tutor_ldap": r[1], "issue_id": r[2], "bind_time": r[3]}
    for r in roster_rows
]

# 2. Day1 已有学习记录的用户
with open(TOOLS / "55f412d8-c6d3-4921-8735-b031d9f4769d.txt") as f:
    day1_data = json.load(f)
day1_rows = day1_data["data"]["rows"]
# columns: user_id, issue_id, status, dbctime, dbutime
day1_keys = {(r[0], r[1]) for r in day1_rows}
day1_status_dist = {}
for r in day1_rows:
    s = r[2]
    day1_status_dist[s] = day1_status_dist.get(s, 0) + 1

print("=== 底盘概况 ===")
issue_cnt = {}
for u in roster:
    issue_cnt[u["issue_id"]] = issue_cnt.get(u["issue_id"], 0) + 1
print(f"A 组 (846): {issue_cnt.get(846, 0)} 人")
print(f"B 组 (847): {issue_cnt.get(847, 0)} 人")
print(f"合计: {len(roster)} 人")

print("\n=== Day1 学习记录分布 ===")
print(f"Day1 有记录用户: {len(day1_keys)} 人")
status_map = {1: "到习", 2: "部分完习", 3: "完习"}
for s, c in sorted(day1_status_dist.items()):
    print(f"  status={s} ({status_map.get(s, '?')}) : {c}")

# 3. Day1 无记录用户
no_attend = [u for u in roster if (u["user_id"], u["issue_id"]) not in day1_keys]
print(f"\n=== Day1 无记录用户 ===")
print(f"总计: {len(no_attend)} 人")
no_attend_by_issue = {}
for u in no_attend:
    no_attend_by_issue[u["issue_id"]] = no_attend_by_issue.get(u["issue_id"], 0) + 1
print(f"A 组 (846): {no_attend_by_issue.get(846, 0)} 人 / 占 A {no_attend_by_issue.get(846, 0)/issue_cnt.get(846,1)*100:.1f}%")
print(f"B 组 (847): {no_attend_by_issue.get(847, 0)} 人 / 占 B {no_attend_by_issue.get(847, 0)/issue_cnt.get(847,1)*100:.1f}%")

# 4. 保存名单
out_csv = BASE / "day1_no_attend_users.csv"
with open(out_csv, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["user_id", "tutor_ldap", "issue_id", "bind_time"])
    w.writeheader()
    w.writerows(no_attend)
print(f"\n名单已写入: {out_csv}")

out_ids = BASE / "user_ids.txt"
with open(out_ids, "w") as f:
    for u in no_attend:
        f.write(f"{u['user_id']}\n")
print(f"user_id 列表: {out_ids}")
