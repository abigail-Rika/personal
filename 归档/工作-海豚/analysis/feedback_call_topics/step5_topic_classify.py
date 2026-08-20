"""
Step 5: 对 22 通反馈电话转写做主题分类

策略：
- 每通电话按句子切段（每 8 句为一个 segment）
- 对每个 segment 统计 7 类主题关键词命中数
- 命中最多 + 阈值的主题作为该 segment 主题
- 累计每主题的总时长

主题定义（与 4 case 标注一致）：
  T1_开场寒暄
  T2_学情复盘
  T3_问题诊断与目标
  T4_产品方案介绍
  T5_长期服务路径
  T6_关单推销
  T7_顾虑承接
"""
import json
import csv
import re
from pathlib import Path
from collections import defaultdict, Counter

BASE = Path(__file__).parent
TR = BASE / "transcripts"

# 主题关键词字典：每个关键词配置权重和位置约束
TOPIC_KEYWORDS = {
    "T1_开场寒暄": {
        "kw": [
            ("你好", 1), ("不好意思", 2), ("打扰", 2), ("辛苦", 2), ("抱歉", 1),
            ("挂", 1), ("再见", 2), ("拜拜", 2), ("结束", 1), ("最后", 1),
            ("祝", 2), ("假期愉快", 2), ("节假日快乐", 2), ("电话给", 2),
        ]
    },
    "T2_学情复盘": {
        "kw": [
            ("学了", 1.5), ("学过", 1), ("感受", 2), ("感觉", 1), ("体验", 1.5),
            ("正确率", 3), ("错题", 1), ("做题", 1.5), ("答题", 2), ("做错", 2),
            ("讲题", 2), ("视频", 1), ("动画", 1.5), ("互动", 1.5),
            ("学情", 3), ("孩子的表现", 3), ("孩子的情况", 3), ("学习情况", 2),
            ("听懂", 1.5), ("理解", 1), ("掌握", 1.5), ("吸收", 1.5),
            ("难度", 1), ("基础", 1), ("会不会", 1), ("能不能", 0.5),
            ("第一题", 2), ("第二题", 2), ("分钟", 1), ("学了几分钟", 2),
            ("报告", 1.5), ("学习报告", 2),
        ]
    },
    "T3_问题诊断与目标": {
        "kw": [
            ("目标", 2), ("想考", 2), ("提高", 1.5), ("薄弱", 2), ("不会", 1.5),
            ("跟不上", 2), ("学不好", 2), ("听不懂", 2), ("瓶颈", 2),
            ("问题", 1), ("难点", 2), ("卡", 1), ("方法", 1.5),
            ("初一", 1), ("初二", 1), ("初三", 1), ("小升初", 2), ("中考", 2),
            ("年级", 1), ("成绩", 1.5), ("分数", 1.5), ("排名", 2),
            ("举一反三", 2), ("721", 3), ("七二一", 3),
            ("拓展", 1), ("重难点", 2), ("基础题", 1.5),
        ]
    },
    "T4_产品方案介绍": {
        "kw": [
            ("错题本", 3), ("资料库", 3), ("学习计划", 2.5), ("学习方法", 2),
            ("知识点", 1.5), ("APP", 2), ("海豚", 0.5),
            ("助理", 2.5), ("助教", 2), ("班主任", 2),
            ("一对一", 2), ("跟踪", 1.5), ("解析", 1.5),
            ("课表", 2), ("每周", 1), ("一周", 1),
            ("机制", 2), ("功能", 2), ("特点", 1.5), ("优势", 1.5),
            ("怎么学", 1.5), ("如何", 0.5), ("流程", 1.5),
            ("AI", 1.5), ("语音", 1.5),
            ("练习", 1.5), ("精讲", 2), ("课程", 1.5),
            ("举一反三", 2),
        ]
    },
    "T5_长期服务路径": {
        "kw": [
            ("长期", 2), ("坚持", 2), ("每天", 1.5), ("天天", 2),
            ("接下来", 1.5), ("后续", 1.5), ("以后", 1.5),
            ("下周", 1.5), ("下个月", 2), ("学期", 1.5),
            ("约定", 2), ("继续", 1.5), ("跟下去", 2),
            ("陪伴", 2), ("服务", 1.5), ("跟进", 2),
            ("半年", 2), ("一年", 1.5), ("一学期", 2),
            ("正式", 1.5), ("正课", 2),
        ]
    },
    "T6_关单推销": {
        # 整体权重 ×1.5 加权（基于审计：关单关键词命中 379 次但段落主导率被产品/学情压制）
        "kw": [
            ("会员", 4.5), ("报名", 4.5), ("付款", 4.5), ("订单", 4), ("下单", 4.5),
            ("年卡", 4.5), ("季卡", 4.5), ("12个月", 4.5), ("24个月", 4.5),
            ("10次", 4), ("20次", 4),
            ("活动", 3), ("优惠", 4), ("便宜", 3), ("特价", 4.5),
            ("现在报", 4), ("今天报", 4), ("名额", 3),
            ("价格", 3), ("一万", 3), ("几千", 3), ("多少钱", 3.5),
            ("分期", 4), ("免息", 4.5), ("白条", 4),
            ("续费", 4), ("加赠", 4.5), ("赠送", 3), ("送", 1.5),
            ("直通车", 4.5), ("正式课", 3), ("正价", 4), ("立减", 4.5),
            ("链接", 3), ("二维码", 3), ("扫码", 4),
            ("买", 1.5), ("课包", 3), ("套餐", 3),
        ]
    },
    "T7_顾虑承接": {
        # 整体权重 ×1.3 加权
        "kw": [
            ("商量", 2.5), ("再想想", 2.5), ("考虑", 2),
            ("孩子爸", 3), ("孩子妈", 2.5), ("老公", 3), ("老婆", 3),
            ("家人", 2), ("商量一下", 3),
            ("补习班", 3), ("辅导班", 3), ("其他机构", 3),
            ("学习机", 2.5), ("学而思", 4), ("猿辅导", 4), ("作业帮", 4),
            ("没时间", 2.5), ("时间不够", 2.5), ("作业多", 2.5), ("住校", 3),
            ("不愿意", 2), ("不想学", 2.5), ("抗拒", 3), ("不配合", 2.5),
            ("贵", 2), ("太贵", 2.5), ("便宜点", 2.5),
            ("退", 2), ("退费", 2.5), ("不退", 2.5),
            ("再说", 2), ("到时候", 1.5),
        ]
    },
}

SEG_SIZE = 8  # 每段 8 句

def classify_segment(sentences):
    """对一段（8 句左右）打主题标签，返回最高分主题（如果都过低返回 None）"""
    text = "".join(s["text"] for s in sentences)
    scores = {}
    for topic, cfg in TOPIC_KEYWORDS.items():
        score = 0.0
        for kw, w in cfg["kw"]:
            cnt = text.count(kw)
            score += cnt * w
        scores[topic] = score
    # 取最高分
    best = max(scores, key=scores.get)
    if scores[best] < 1.0:
        return None, scores
    return best, scores


def process_call(call_id_safe, transcript_path):
    with open(transcript_path) as f:
        try:
            data = json.load(f)
        except Exception as e:
            return None
    if not isinstance(data, list):
        return None
    # 过滤空
    sentences = [s for s in data if s.get("text") and s.get("startTime") and s.get("endTime")]
    if not sentences:
        return None
    # 按 startTime 升序
    sentences.sort(key=lambda x: int(x["startTime"]))

    # 切段
    segs = []
    for i in range(0, len(sentences), SEG_SIZE):
        seg = sentences[i:i + SEG_SIZE]
        topic, _ = classify_segment(seg)
        seg_start = int(seg[0]["startTime"])
        seg_end = int(seg[-1]["endTime"])
        seg_dur = max(0, seg_end - seg_start)
        # 第一/最后一段如果未分类，倾向于开场/结束
        if topic is None:
            if i == 0:
                topic = "T1_开场寒暄"
            elif i + SEG_SIZE >= len(sentences):
                topic = "T1_开场寒暄"
            else:
                topic = "T9_其他"
        segs.append({"start": seg_start, "end": seg_end, "duration_ms": seg_dur, "topic": topic})

    # 汇总
    by_topic = defaultdict(int)
    by_topic_segs = defaultdict(int)
    for s in segs:
        by_topic[s["topic"]] += s["duration_ms"]
        by_topic_segs[s["topic"]] += 1
    total_ms = sum(s["duration_ms"] for s in segs)
    return {
        "n_segs": len(segs),
        "total_ms": total_ms,
        "by_topic_ms": dict(by_topic),
        "by_topic_seg": dict(by_topic_segs),
        "segs": segs,
    }


def safe_filename(call_id: str) -> str:
    return call_id.replace(":", "_").replace("/", "_")


def main():
    # 加载匹配电话
    with open(BASE / "matched_calls.csv") as f:
        rows = list(csv.DictReader(f))

    results = []
    for r in rows:
        cid = r["call_id"]
        path = TR / f"{safe_filename(cid)}.json"
        if not path.exists():
            print(f"MISSING: {cid}")
            continue
        res = process_call(cid, path)
        if res is None:
            print(f"PARSE FAIL: {cid}")
            continue
        res["call_id"] = cid
        res["user_id"] = r["user_id"]
        res["tutor_ldap"] = r["tutor_ldap"]
        res["comm_type"] = r["comm_type"]
        res["duration_db"] = int(r["duration"])
        results.append(res)
        print(f"[{r['user_id']}] {cid[:30]:<32} n_segs={res['n_segs']:>3} total={res['total_ms']/60000:>5.1f}min")

    # === 汇总 ===
    print("\n" + "=" * 80)
    print(f"汇总: {len(results)} 通电话")
    print("=" * 80)

    total_ms_all = sum(r["total_ms"] for r in results)
    print(f"总时长: {total_ms_all/60000:.1f} 分钟 / {total_ms_all/3600000:.1f} 小时")
    print(f"平均通话: {total_ms_all/len(results)/60000:.1f} 分钟")

    agg = defaultdict(int)
    for r in results:
        for t, ms in r["by_topic_ms"].items():
            agg[t] += ms
    print("\n主题时长占比:")
    rows_sorted = sorted(agg.items(), key=lambda kv: -kv[1])
    for t, ms in rows_sorted:
        pct = ms / total_ms_all * 100 if total_ms_all else 0
        print(f"  {t:<24} {ms/60000:>6.1f} min  {pct:>5.1f}%")

    # 命中率
    hits = defaultdict(int)
    for r in results:
        for t in r["by_topic_ms"]:
            hits[t] += 1
    print("\n主题命中率（出现在多少通电话中）:")
    for t, h in sorted(hits.items(), key=lambda kv: -kv[1]):
        print(f"  {t:<24} {h}/{len(results)} 通")

    # 写明细
    out = BASE / "call_topic_breakdown.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        topics = sorted(TOPIC_KEYWORDS.keys()) + ["T9_其他"]
        fields = ["call_id", "user_id", "tutor_ldap", "comm_type", "duration_db_s", "total_min"] + [f"{t}_min" for t in topics] + [f"{t}_pct" for t in topics]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in results:
            row = {
                "call_id": r["call_id"],
                "user_id": r["user_id"],
                "tutor_ldap": r["tutor_ldap"],
                "comm_type": r["comm_type"],
                "duration_db_s": r["duration_db"],
                "total_min": round(r["total_ms"] / 60000, 1),
            }
            for t in topics:
                ms = r["by_topic_ms"].get(t, 0)
                row[f"{t}_min"] = round(ms / 60000, 1)
                row[f"{t}_pct"] = round(ms / r["total_ms"] * 100, 1) if r["total_ms"] else 0
            w.writerow(row)
    print(f"\n明细已写入: {out}")

    # 写汇总 JSON
    summary = {
        "n_calls": len(results),
        "total_min": round(total_ms_all / 60000, 1),
        "avg_call_min": round(total_ms_all / len(results) / 60000, 1) if results else 0,
        "topic_aggregate": {
            t: {"min": round(ms / 60000, 1), "pct": round(ms / total_ms_all * 100, 1)}
            for t, ms in rows_sorted
        },
        "topic_hits": {t: f"{h}/{len(results)}" for t, h in hits.items()},
    }
    with open(BASE / "topic_summary.json", "w") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"汇总已写入: topic_summary.json")

    return results


if __name__ == "__main__":
    main()
