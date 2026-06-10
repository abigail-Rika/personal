"""审计：扫描每通转写里的关单/产品/学情类关键词出现频次"""
import json
import csv
from pathlib import Path

BASE = Path(__file__).parent
TR = BASE / "transcripts"

with open(BASE / "matched_calls.csv") as f:
    rows = list(csv.DictReader(f))

KW_GROUPS = {
    "关单": ["会员", "报名", "价格", "优惠", "多少钱", "链接", "订单", "下单", "付款", "支付", "便宜", "活动", "现在报", "今天报", "限时", "立减", "续费", "全款", "分期", "免息", "买", "课包"],
    "产品": ["错题本", "资料库", "学习计划", "学习方法", "助理", "助教", "班主任", "举一反三"],
    "学情": ["学情", "正确率", "做错", "答题", "讲题", "做题", "视频", "动画", "互动", "完习", "学了", "学过"],
    "诊断": ["目标", "提高", "薄弱", "跟不上", "听不懂", "成绩", "分数", "难点", "弱项"],
    "长期": ["每天", "天天", "下周", "下个月", "学期", "坚持", "正式课", "正课"],
    "顾虑": ["商量", "孩子爸", "老公", "补习班", "学而思", "猿辅导", "没时间", "住校", "贵", "再想想", "考虑", "退"],
}


def safe(s):
    return s.replace(":", "_").replace("/", "_")


print(f"{'call_id':<40} {'user':<11} {'min':>5} | {' | '.join(f'{k:>5}' for k in KW_GROUPS)}")
for r in rows:
    path = TR / f"{safe(r['call_id'])}.json"
    if not path.exists():
        continue
    with open(path) as f:
        d = json.load(f)
    text = "".join(s.get("text", "") for s in d)
    cnts = {}
    for g, kws in KW_GROUPS.items():
        cnts[g] = sum(text.count(k) for k in kws)
    dur_min = int(r["duration"]) / 60
    print(f"{r['call_id'][:40]:<40} {r['user_id']:<11} {dur_min:>5.1f} | " + " | ".join(f"{cnts[k]:>5}" for k in KW_GROUPS))

# 总计
print("\n=== 全样本关键词总次数 ===")
totals = {k: 0 for k in KW_GROUPS}
for r in rows:
    path = TR / f"{safe(r['call_id'])}.json"
    if not path.exists():
        continue
    with open(path) as f:
        d = json.load(f)
    text = "".join(s.get("text", "") for s in d)
    for g, kws in KW_GROUPS.items():
        totals[g] += sum(text.count(k) for k in kws)
for g, c in totals.items():
    print(f"  {g}: {c}")
