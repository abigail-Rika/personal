"""
Step 6: 汇总报告 - 按时长/通话类型分桶
"""
import csv
import json
from pathlib import Path
from collections import defaultdict

BASE = Path(__file__).parent

with open(BASE / "call_topic_breakdown.csv") as f:
    rows = list(csv.DictReader(f))

TOPICS = ["T1_开场寒暄", "T2_学情复盘", "T3_问题诊断与目标", "T4_产品方案介绍",
          "T5_长期服务路径", "T6_关单推销", "T7_顾虑承接", "T9_其他"]


def to_float(v): return float(v) if v else 0.0


def aggregate(rows):
    total_min = sum(to_float(r["total_min"]) for r in rows)
    agg = {}
    for t in TOPICS:
        m = sum(to_float(r[f"{t}_min"]) for r in rows)
        agg[t] = {"min": round(m, 1), "pct": round(m / total_min * 100, 1) if total_min else 0}
    return total_min, agg


# 总体
total_min, all_agg = aggregate(rows)
print("=" * 80)
print(f"【全样本】{len(rows)} 通 / {total_min:.1f} min / 平均 {total_min/len(rows):.1f} min")
print("=" * 80)
for t in sorted(all_agg, key=lambda x: -all_agg[x]["pct"]):
    a = all_agg[t]
    print(f"  {t:<24} {a['min']:>6.1f} min  {a['pct']:>5.1f}%")

# 按时长分桶
print("\n" + "=" * 80)
print("【按时长分桶】")
print("=" * 80)
buckets = {
    "短(<10min)": lambda r: to_float(r["total_min"]) < 10,
    "中(10-30min)": lambda r: 10 <= to_float(r["total_min"]) < 30,
    "长(30-45min)": lambda r: 30 <= to_float(r["total_min"]) < 45,
    "超长(>=45min)": lambda r: to_float(r["total_min"]) >= 45,
}
for name, fn in buckets.items():
    sub = [r for r in rows if fn(r)]
    if not sub:
        continue
    sub_total, sub_agg = aggregate(sub)
    print(f"\n--- {name} ({len(sub)} 通 / {sub_total:.1f} min / 平均 {sub_total/len(sub):.1f} min) ---")
    for t in TOPICS:
        a = sub_agg[t]
        bar = "█" * int(a["pct"] / 2)
        print(f"  {t:<24} {a['pct']:>5.1f}% {bar}")

# 按 comm_type 分桶
print("\n" + "=" * 80)
print("【按反馈类型分桶】")
print("=" * 80)
for ct, label in [("25", "type25 反馈关单"), ("69", "type69 完习回访")]:
    sub = [r for r in rows if r["comm_type"] == ct]
    if not sub:
        continue
    sub_total, sub_agg = aggregate(sub)
    print(f"\n--- {label} ({len(sub)} 通 / {sub_total:.1f} min / 平均 {sub_total/len(sub):.1f} min) ---")
    for t in TOPICS:
        a = sub_agg[t]
        bar = "█" * int(a["pct"] / 2)
        print(f"  {t:<24} {a['pct']:>5.1f}% {bar}")

# 通话内部主题"丰富度"：每通电话有多少种主题命中
print("\n" + "=" * 80)
print("【单通主题丰富度】")
print("=" * 80)
for r in rows:
    n = sum(1 for t in TOPICS if to_float(r[f"{t}_min"]) > 0.5)
    print(f"  {r['call_id'][:30]:<32} {r['user_id']:<11} {float(r['total_min']):>5.1f}min  主题数={n}/8")
