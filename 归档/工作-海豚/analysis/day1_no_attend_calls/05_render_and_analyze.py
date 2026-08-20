"""
1. 把每通转写渲染成可读对话文本（user_id 排序后导出 markdown）
2. 对每通做结构化诊断：
   - 是否真的接通（用户是否说过 >= 2 句）
   - 销售开场动作
   - 是否提到孩子开始学习 / Day1 / 当天任务
   - 是否给出最小可执行任务（"今晚 / 明天做 XXX"）
   - 是否解释操作步骤（下载 / 登录 / 入口）
   - 用户态度（接受/犹豫/敷衍/拒绝/挂断）
   - 关键摘录
"""
import csv
import json
import re
from pathlib import Path

BASE = Path(__file__).parent
TR_DIR = BASE / "transcripts"
RENDER_DIR = BASE / "rendered"
RENDER_DIR.mkdir(exist_ok=True)


KEYWORDS = {
    "day1_promise": ["今晚", "今天", "明天", "马上", "等一下", "等下", "等会", "现在"],
    "min_task": ["完成", "做一下", "做一节", "学一节", "学完", "学一下", "听一下", "刷一下", "打开", "登录", "进去", "试一下", "体验一下"],
    "introductory_test": ["入门测", "测一下", "测评", "测试"],
    "ai_class": ["动画", "动画课", "AI", "互动课", "课程", "课件", "课节"],
    "objection": ["不需要", "不用了", "再说", "考虑", "退", "不想", "没时间", "太忙", "在忙", "在开车", "在上班", "等会再说"],
    "operation_pain": ["下载", "登录", "找不到", "不会", "在哪", "怎么", "卡", "无法", "打不开"],
    "feedback_promise": ["反馈", "评估", "建议", "总结", "结果", "诊断", "分析"],
    "rejection_hangup": ["再见", "拜拜", "挂了", "回头"],
}


def render(transcript):
    lines = []
    for seg in transcript:
        who = "[销售]" if seg.get("identityType") == "teacher" else "[家长]"
        t_start_ms = int(seg.get("startTime", "0") or 0)
        mm = t_start_ms // 60000
        ss = (t_start_ms % 60000) // 1000
        lines.append(f"{mm:02d}:{ss:02d} {who} {seg.get('text', '').strip()}")
    return "\n".join(lines)


def keyword_hit(text, words):
    return [w for w in words if w in text]


def analyze(transcript):
    teacher_text = " ".join([s["text"] for s in transcript if s.get("identityType") == "teacher"])
    customer_text = " ".join([s["text"] for s in transcript if s.get("identityType") != "teacher"])
    customer_segs = [s for s in transcript if s.get("identityType") != "teacher"]
    teacher_segs = [s for s in transcript if s.get("identityType") == "teacher"]

    # 判断是否真的接通
    customer_words = sum(len(s["text"]) for s in customer_segs)
    teacher_words = sum(len(s["text"]) for s in teacher_segs)
    answered = len(customer_segs) >= 3 and customer_words >= 20

    hits = {k: keyword_hit(teacher_text, v) for k, v in KEYWORDS.items()}
    customer_objection = keyword_hit(customer_text, KEYWORDS["objection"])

    # 是否给出 Day1 当天/今晚的具体任务
    min_task_phrase = []
    for seg in teacher_segs:
        t = seg["text"]
        if any(w in t for w in ["今晚", "今天", "明天", "马上", "现在", "等下", "等会"]):
            if any(w in t for w in ["学", "做", "完成", "听", "打开", "登录", "试", "体验"]):
                min_task_phrase.append(t[:80])

    # 用户态度判断（粗）
    if not answered:
        attitude = "未真正接通"
    elif customer_objection:
        attitude = f"有顾虑/拒绝({','.join(list(set(customer_objection))[:3])})"
    elif customer_words > teacher_words * 0.3:
        attitude = "正常对话"
    else:
        attitude = "被动接收（用户极少说话）"

    return {
        "answered": answered,
        "teacher_words": teacher_words,
        "customer_words": customer_words,
        "customer_seg_count": len(customer_segs),
        "teacher_seg_count": len(teacher_segs),
        "hits": hits,
        "customer_objection": customer_objection,
        "min_task_phrases": min_task_phrase[:3],
        "attitude": attitude,
    }


def main():
    with open(BASE / "sample_20.csv") as f:
        rows = list(csv.DictReader(f))

    results = []
    for r in rows:
        path = TR_DIR / f"u{r['user_id']}_t{r['tutor_ldap']}_d{r['duration_s']}s.json"
        with open(path) as f:
            t = json.load(f)
        rendered = render(t)
        out_md = RENDER_DIR / f"u{r['user_id']}_t{r['tutor_ldap']}_d{r['duration_s']}s.md"
        with open(out_md, "w", encoding="utf-8") as f:
            f.write(f"# 通话转写 - user {r['user_id']}\n\n")
            f.write(f"- issue_id: {r['issue_id']}\n")
            f.write(f"- 销售 (tutor_ldap): {r['tutor_ldap']}\n")
            f.write(f"- 时长: {r['duration_s']}s ({r['duration_min']} min)\n")
            f.write(f"- 开始时间: {r['start_time']}\n\n")
            f.write("```\n")
            f.write(rendered)
            f.write("\n```\n")
        ana = analyze(t)
        results.append({
            "user_id": r["user_id"],
            "issue_id": r["issue_id"],
            "tutor_ldap": r["tutor_ldap"],
            "duration_s": r["duration_s"],
            "start_time": r["start_time"],
            "answered": ana["answered"],
            "attitude": ana["attitude"],
            "teacher_segs": ana["teacher_seg_count"],
            "customer_segs": ana["customer_seg_count"],
            "hits_day1": ",".join(set(ana["hits"]["day1_promise"])),
            "hits_min_task": ",".join(set(ana["hits"]["min_task"])),
            "hits_introtest": ",".join(set(ana["hits"]["introductory_test"])),
            "hits_ai_class": ",".join(set(ana["hits"]["ai_class"])),
            "hits_operation_pain": ",".join(set(ana["hits"]["operation_pain"])),
            "hits_feedback_promise": ",".join(set(ana["hits"]["feedback_promise"])),
            "customer_objection": ",".join(set(ana["customer_objection"])),
            "min_task_phrase_1": ana["min_task_phrases"][0] if ana["min_task_phrases"] else "",
        })

    # 输出诊断表
    out_csv = BASE / "diagnostic.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        w.writerows(results)
    print(f"诊断表: {out_csv}")

    # 文字摘要
    print("\n=== 关键统计 ===")
    answered = [r for r in results if r["answered"]]
    print(f"接通: {len(answered)}/20")
    have_day1 = [r for r in answered if r["hits_day1"]]
    print(f"接通的通话里销售提到 '今晚/今天/明天/现在' 类时间锚: {len(have_day1)}")
    have_min_task = [r for r in answered if r["min_task_phrase_1"]]
    print(f"接通的通话里销售明确说出 '时间锚 + 学/做/完成' 类最小任务句: {len(have_min_task)}")
    have_op_pain = [r for r in results if r["hits_operation_pain"]]
    print(f"通话中出现下载/登录/找不到等操作信号: {len(have_op_pain)}")
    have_objection = [r for r in results if r["customer_objection"]]
    print(f"家长有明确顾虑/拒绝/在忙等表态: {len(have_objection)}")

    print("\n=== 单通诊断 ===")
    for r in results:
        print(f"\n[user={r['user_id']} | {r['tutor_ldap']} | {r['duration_s']}s | {r['start_time'] or '时间未知'}]")
        print(f"  接通: {r['answered']} | 态度: {r['attitude']}")
        print(f"  Day1 时间锚: {r['hits_day1'] or '无'}")
        print(f"  最小任务关键词: {r['hits_min_task'] or '无'}")
        if r["min_task_phrase_1"]:
            print(f"  → 最小任务句: {r['min_task_phrase_1']}")
        print(f"  入门测提及: {r['hits_introtest'] or '无'}")
        print(f"  反馈承诺: {r['hits_feedback_promise'] or '无'}")
        print(f"  操作障碍信号: {r['hits_operation_pain'] or '无'}")
        if r["customer_objection"]:
            print(f"  家长顾虑: {r['customer_objection']}")


if __name__ == "__main__":
    main()
