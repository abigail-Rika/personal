"""
合并两批通话数据，按 user_id 取首通（销售发起、≥60s、成功）
首通定义：班期内、call_type=1（呼出）、status=1（成功）、duration>=60 的最早一通
"""
import json
import csv
import re
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).parent

BATCH_FILES = [
    ("batch1", BASE / "raw_batch1.json"),
    ("batch2", BASE / "raw_batch2.json"),
]


def parse_time_from_call_id(call_id: str):
    """从 call_id 前缀提取 13 位毫秒时间戳，例如 '1777465835585:15923377609:xxx'"""
    m = re.match(r"^(\d{13}):", call_id)
    if m:
        return int(m.group(1))
    return None


def load_calls():
    all_calls = []
    for tag, path in BATCH_FILES:
        with open(path) as f:
            d = json.load(f)
        rows = d["data"]["rows"]
        for r in rows:
            ytk_user_id, tutor_ldap, call_id, start_time_mills, duration, status, call_text_url = r
            ts = start_time_mills
            if ts is None:
                ts = parse_time_from_call_id(call_id or "")
            all_calls.append({
                "user_id": ytk_user_id,
                "tutor_ldap": tutor_ldap,
                "call_id": call_id,
                "start_time_mills": start_time_mills,
                "duration": duration,
                "status": status,
                "call_text_url": call_text_url,
                "ts_estimated": ts,
                "ts_source": "field" if start_time_mills else ("call_id" if ts else "missing"),
                "batch": tag,
            })
    return all_calls


def main():
    calls = load_calls()
    print(f"Total calls (>=60s, outgoing, success): {len(calls)}")

    by_user = {}
    for c in calls:
        by_user.setdefault(c["user_id"], []).append(c)
    print(f"Distinct users with at least 1 qualifying call: {len(by_user)}")

    # 时间字段来源分布
    src_dist = {}
    for c in calls:
        src_dist[c["ts_source"]] = src_dist.get(c["ts_source"], 0) + 1
    print(f"Timestamp source: {src_dist}")

    # 加载底盘做关联
    no_attend = []
    with open(BASE / "day1_no_attend_users.csv") as f:
        reader = csv.DictReader(f)
        for row in reader:
            no_attend.append(row)
    no_attend_ids = {int(r["user_id"]) for r in no_attend}
    print(f"Day1 无记录用户总数: {len(no_attend_ids)}")
    print(f"其中有匹配电话: {len([u for u in no_attend_ids if u in by_user])}")
    print(f"其中无匹配电话: {len([u for u in no_attend_ids if u not in by_user])}")

    # 每人取首通（按估计时间最早）
    first_calls = []
    for uid, cs in by_user.items():
        # missing 的放最后
        sorted_cs = sorted(cs, key=lambda x: (x["ts_estimated"] is None, x["ts_estimated"] or 0))
        first_calls.append(sorted_cs[0])
    print(f"首通数: {len(first_calls)}")

    # 有转写 URL 的
    with_text = [c for c in first_calls if c["call_text_url"]]
    print(f"首通中有 call_text_url 的: {len(with_text)}")

    # 按时间排序，输出
    first_calls_sorted = sorted(
        first_calls,
        key=lambda x: (x["ts_estimated"] is None, x["ts_estimated"] or 0),
    )

    # 补 issue / 真实时间字符串
    issue_of = {int(r["user_id"]): int(r["issue_id"]) for r in no_attend}

    out_rows = []
    for c in first_calls_sorted:
        ts = c["ts_estimated"]
        ts_str = ""
        if ts:
            ts_str = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M:%S")
        out_rows.append({
            "user_id": c["user_id"],
            "issue_id": issue_of.get(c["user_id"], ""),
            "tutor_ldap": c["tutor_ldap"],
            "call_id": c["call_id"],
            "start_time": ts_str,
            "duration_s": c["duration"],
            "duration_min": round(c["duration"] / 60, 1),
            "call_text_url": c["call_text_url"] or "",
            "ts_source": c["ts_source"],
        })

    out_csv = BASE / "first_calls.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)
    print(f"首通明细已写入: {out_csv}")

    # 时长分布
    bucket = {"60-120s": 0, "120-300s": 0, "300-600s": 0, "600-1200s": 0, "1200s+": 0}
    for c in first_calls:
        d = c["duration"]
        if d < 120:
            bucket["60-120s"] += 1
        elif d < 300:
            bucket["120-300s"] += 1
        elif d < 600:
            bucket["300-600s"] += 1
        elif d < 1200:
            bucket["600-1200s"] += 1
        else:
            bucket["1200s+"] += 1
    print("首通时长分布:")
    for k, v in bucket.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
