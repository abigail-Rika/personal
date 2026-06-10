"""
按时长 4 桶 + 销售多样化抽 20 通有转写的首通
"""
import csv
import random
from pathlib import Path
from collections import defaultdict

BASE = Path(__file__).parent
random.seed(42)

with open(BASE / "first_calls.csv") as f:
    rows = [r for r in csv.DictReader(f) if r["call_text_url"]]

print(f"候选首通（有转写）: {len(rows)}")

buckets = {
    "60-120s": [],
    "120-300s": [],
    "300-600s": [],
    "600s+": [],
}
for r in rows:
    d = int(r["duration_s"])
    if d < 120:
        buckets["60-120s"].append(r)
    elif d < 300:
        buckets["120-300s"].append(r)
    elif d < 600:
        buckets["300-600s"].append(r)
    else:
        buckets["600s+"].append(r)

print("候选分桶:")
for k, v in buckets.items():
    print(f"  {k}: {len(v)}")

target_per_bucket = 5
sampled = []
used_tutors = defaultdict(int)
for k, vs in buckets.items():
    random.shuffle(vs)
    vs_sorted = sorted(vs, key=lambda x: used_tutors[x["tutor_ldap"]])
    pick = []
    for v in vs_sorted:
        if len(pick) >= target_per_bucket:
            break
        pick.append(v)
        used_tutors[v["tutor_ldap"]] += 1
    sampled.extend(pick)

print(f"\n抽样 {len(sampled)} 通，覆盖 {len(set(s['tutor_ldap'] for s in sampled))} 个销售")
print(f"涉及销售: {sorted(set(s['tutor_ldap'] for s in sampled))}")

out = BASE / "sample_20.csv"
with open(out, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(sampled[0].keys()))
    w.writeheader()
    for s in sampled:
        w.writerow(s)
print(f"\n抽样名单: {out}")

print("\n抽样明细:")
for i, s in enumerate(sampled, 1):
    print(f"  {i:2d}. user={s['user_id']} | issue={s['issue_id']} | tutor={s['tutor_ldap']:20s} | dur={s['duration_s']}s ({s['duration_min']}min) | time={s['start_time']}")
