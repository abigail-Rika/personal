"""
Step 3: 把抽样用户的反馈记录与候选电话做匹配
匹配规则（skill 默认）：
  反馈记录 type25/69 锚点 → 前 2h 内同老师同用户最近一通 status=1 且有 call_text_url 的电话

输入：
  - sampled_users.json: 20 个 user_id + 锚点反馈记录
  - 候选电话 JSON 文件（call_data_77.json，从最新 sql 结果存）

输出：
  - matched_calls.csv: 20 个用户对应的匹配电话明细
"""
import json
import csv
from pathlib import Path

BASE = Path(__file__).parent

# 加载抽样用户
with open(BASE / "sampled_users.json") as f:
    sampled = json.load(f)
sampled_map = {s["user_id"]: s for s in sampled}

# 加载候选电话（从下方的 mcp 返回手动落盘）
with open(BASE / "candidate_calls.json") as f:
    call_data = json.load(f)
rows = call_data["data"]["rows"]
# columns: ytk_user_id, tutor_ldap, call_id, dbc_ts, start_time, start_time_mills, duration, type, call_text_url
calls_by_user_tutor = {}
calls_by_user = {}  # 兜底：不限老师
for r in rows:
    uid, tutor, cid, dbc_ts, st, stms, dur, ctype, url = r
    # 用 start_time（秒）兜底，缺失时用 dbc_ts - duration
    if st is not None:
        call_ts = int(st)
    elif dbc_ts is not None:
        call_ts = int(float(dbc_ts)) - dur
    else:
        continue
    entry = {
        "call_id": cid,
        "tutor_ldap_call": tutor,
        "call_ts": call_ts,
        "duration": dur,
        "type": ctype,
        "url": url,
    }
    calls_by_user_tutor.setdefault((uid, tutor), []).append(entry)
    calls_by_user.setdefault(uid, []).append(entry)

print(f"候选电话总数: {len(rows)}")
print(f"涉及 (user, tutor) 对: {len(calls_by_user_tutor)}")

# 匹配
matched = []
unmatched = []
for s in sampled:
    uid = s["user_id"]
    tutor = s["tutor_ldap"]
    fb_ts = s["comm_ts"]
    key = (uid, tutor)
    candidates = calls_by_user_tutor.get(key, [])
    # 反馈记录前 2h 内（fb_ts - 7200 <= call_ts < fb_ts）
    window = [c for c in candidates if (fb_ts - 7200) <= c["call_ts"] < fb_ts]
    if not window:
        # 退而求其次：放宽到反馈前 6h 内
        window2 = [c for c in candidates if (fb_ts - 21600) <= c["call_ts"] < fb_ts]
        if window2:
            best = max(window2, key=lambda c: c["call_ts"])
            matched.append({
                "user_id": uid,
                "tutor_ldap": tutor,
                "comm_type": s["comm_type"],
                "comm_ts": fb_ts,
                "match_window": "0-6h",
                **best,
            })
        else:
            # 再退：放宽到反馈前 24h
            window3 = [c for c in candidates if (fb_ts - 86400) <= c["call_ts"] < fb_ts]
            if window3:
                best = max(window3, key=lambda c: c["call_ts"])
                matched.append({
                    "user_id": uid,
                    "tutor_ldap": tutor,
                    "comm_type": s["comm_type"],
                    "comm_ts": fb_ts,
                    "match_window": "0-24h",
                    **best,
                })
            else:
                # 任意时间内最近一通（同老师）
                if candidates:
                    before = [c for c in candidates if c["call_ts"] < fb_ts]
                    if before:
                        best = max(before, key=lambda c: c["call_ts"])
                        matched.append({
                            "user_id": uid,
                            "tutor_ldap": tutor,
                            "comm_type": s["comm_type"],
                            "comm_ts": fb_ts,
                            "match_window": "同老师>24h",
                            **best,
                        })
                        continue
                # 兜底：放宽老师约束（反馈关单可能由换交后销售写入），找该用户反馈前 2h 内任意销售电话
                any_calls = calls_by_user.get(uid, [])
                any_window = [c for c in any_calls if (fb_ts - 7200) <= c["call_ts"] < fb_ts]
                if any_window:
                    best = max(any_window, key=lambda c: c["call_ts"])
                    matched.append({
                        "user_id": uid,
                        "tutor_ldap": tutor,
                        "comm_type": s["comm_type"],
                        "comm_ts": fb_ts,
                        "match_window": "0-2h(跨老师)",
                        **best,
                    })
                    continue
                # 再宽：跨老师任意时间 before
                any_before = [c for c in any_calls if c["call_ts"] < fb_ts]
                if any_before:
                    best = max(any_before, key=lambda c: c["call_ts"])
                    matched.append({
                        "user_id": uid,
                        "tutor_ldap": tutor,
                        "comm_type": s["comm_type"],
                        "comm_ts": fb_ts,
                        "match_window": "跨老师>24h",
                        **best,
                    })
                    continue
                unmatched.append((uid, tutor, fb_ts, "no_call_at_all"))
    else:
        # 取窗口内最近一通（最接近反馈时间）
        best = max(window, key=lambda c: c["call_ts"])
        matched.append({
            "user_id": uid,
            "tutor_ldap": tutor,
            "comm_type": s["comm_type"],
            "comm_ts": fb_ts,
            "match_window": "0-2h",
            **best,
        })

print(f"\n匹配成功: {len(matched)} / {len(sampled)}")
print(f"未匹配: {len(unmatched)}")
for u in unmatched:
    print(f"  {u}")

# 匹配窗口分布
from collections import Counter
win_dist = Counter(m["match_window"] for m in matched)
print(f"\n匹配窗口分布: {dict(win_dist)}")

# 输出 csv
out = BASE / "matched_calls.csv"
fields = ["user_id", "tutor_ldap", "comm_type", "comm_ts", "match_window",
          "call_id", "tutor_ldap_call", "call_ts", "duration", "type", "url"]
with open(out, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(matched)
print(f"\n已写入: {out}")

# 时长分布
durs = [m["duration"] for m in matched]
print(f"\n匹配电话时长（秒）: min={min(durs)} max={max(durs)} avg={sum(durs)/len(durs):.0f}")
print(f"  <300s: {sum(1 for d in durs if d < 300)}")
print(f"  300-600s: {sum(1 for d in durs if 300 <= d < 600)}")
print(f"  600-1200s: {sum(1 for d in durs if 600 <= d < 1200)}")
print(f"  >=1200s: {sum(1 for d in durs if d >= 1200)}")
