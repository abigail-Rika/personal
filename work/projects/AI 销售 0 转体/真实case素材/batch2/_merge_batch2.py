#!/usr/bin/env python3
"""把 case6-case10 的通话+微信整理为统一格式的时间线，并放回 真实case素材/ 根目录。

通话文本：JSON 数组，每条 {identityType, text, startTime(ms 相对), endTime(ms 相对)}
微信消息：JSON 数组（已按 createdTime 倒序），每条 {senderRemoteId, receiverRemoteId, content:{...}, createdTime}
"""
import json
import os
import datetime as dt

BASE = "/Users/jiwenyue/Abigial/personal/work/projects/AI 销售 0 转体/真实case素材"
BATCH = os.path.join(BASE, "batch2")


def load_call(path, start_dt, label_suffix=""):
    """通话文本：startTime/endTime 是相对毫秒"""
    with open(path) as f:
        segs = json.load(f)
    out = []
    base_ts = start_dt.timestamp()
    for s in segs:
        rel_ms = int(s.get('startTime', 0))
        abs_ts = base_ts + rel_ms / 1000
        role = '销售' if s.get('identityType') == 'teacher' else '家长'
        text = (s.get('text', '') or '').strip()
        if not text:
            continue
        out.append({'ts': abs_ts, 'role': role, 'text': text, 'source': 'call', 'label': label_suffix})
    out.sort(key=lambda x: x['ts'])
    return out


def merge_call_lines(segs):
    if not segs:
        return []
    merged = []
    cur = dict(segs[0])
    for s in segs[1:]:
        if s['role'] == cur['role'] and s['ts'] - cur['ts'] < 3.5:
            cur['text'] = cur['text'] + ' ' + s['text']
        else:
            merged.append(cur)
            cur = dict(s)
    merged.append(cur)
    return merged


def load_wechat(path, tutor_id, user_id, label=''):
    with open(path) as f:
        msgs = json.load(f)
    out = []
    for m in msgs:
        c = m.get('content', {}) or {}
        ct = c.get('contentType', '')
        ts = m.get('createdTime', 0)
        sender = str(m.get('senderRemoteId', ''))
        if sender == str(tutor_id):
            role = '销售'
        elif sender == str(user_id):
            role = '家长'
        else:
            role = '?'
        if ct == 'TEXT':
            text = c.get('content', '')
        elif ct == 'PICTURE':
            bp = c.get('bigPicture') if isinstance(c.get('bigPicture'), dict) else None
            url = bp.get('url', '') if bp else ''
            text = f'[图片] {url[:60]}...' if url else '[图片]'
        elif ct == 'SYSTEM':
            text = '[系统] ' + (c.get('content', '') or '')
            role = '系统'
        else:
            text = f'[{ct}]'
            # 兜底保留内容
            content_str = c.get('content')
            if isinstance(content_str, str) and content_str:
                text += ' ' + content_str[:120]
        out.append({'ts': ts, 'role': role, 'text': text, 'source': 'wx', 'label': label})
    out.sort(key=lambda x: x['ts'])
    return out


def write_case(events, header_md, out_path):
    lines = [header_md, '']
    cur_day = None
    cur_block = None  # ('call', label) or ('wx', label)
    for e in events:
        day = dt.datetime.fromtimestamp(e['ts']).strftime('%Y-%m-%d %A')
        if day != cur_day:
            lines.append('')
            lines.append(f'## {day}')
            lines.append('')
            cur_day = day
            cur_block = None
        block_key = (e['source'], e.get('label', ''))
        if block_key != cur_block:
            if e['source'] == 'call':
                suffix = f' · {e.get("label","")}' if e.get('label') else ''
                lines.append('')
                lines.append(f'### 📞 通话{suffix}')
                lines.append('')
            else:
                label = e.get('label', '')
                lines.append('')
                lines.append(f'### 💬 微信 · {label}')
                lines.append('')
            cur_block = block_key
        ts_str = dt.datetime.fromtimestamp(e['ts']).strftime('%H:%M:%S')
        role = e['role']
        text = e['text'].replace('\n', '\n  ')
        if role == '销售':
            lines.append(f'- `{ts_str}` **销售**：{text}')
        elif role == '家长':
            lines.append(f'- `{ts_str}` 家长：{text}')
        elif role == '系统':
            lines.append(f'- `{ts_str}` _{text}_')
        else:
            lines.append(f'- `{ts_str}` ?: {text}')
    with open(out_path, 'w') as f:
        f.write('\n'.join(lines))
    print(f'wrote {out_path}: {len(events)} events')


# ============================================================
# Case 6 · user_id=20315279（七年级 / 直投 zt-planPage-0-5 / huxinzz05 / 0 接通 / 未成单）
# ============================================================
case6_events = []  # 无微信会话；2 通通话 duration=0 且 call_text_url=null，无文本可用
case6_header = """# Case 6 · 初一直投留资·彻底零沟通（user_id=20315279）完整时间线

> **画像**：七年级（初一）学生，**性别/姓名/接听人未知**（电话全部未接通）。  
> **渠道**：APP 专题页学习计划页 `zhaohui-zt-planPage-0-5`（直投留资型）。  
> **销售**：`huxinzz05`（贺心·**同 case3 成单的销售**）。  
> **结局**：进班 issue 620（2026-04-08 08:50）→ **2 通外呼均 0 接通且无录音文本**（DB `status=3`「用户拒绝」）→ status=1 已释放。  
>
> **数据规模**：2 通外呼 0 接通无文本 + **0 个微信会话**（DB `class_user_wx_chat_msg_stat` 无任何 vid 映射，几乎可确认**未加微**）。  
>
> ⚠️ **关键**：该 case 整个销售跟进周期里**销售从未与家长建立任何沟通通道**。case 进入分析的意义是说明──"线索分配 ≠ 销售机会"，背后是「外呼时机」「号码质量」「未加微闭环」这三个上游问题，而不是话术问题。

## 2026-04-08 Wednesday · 进班当天与销售跟进窗口


### 📞 外呼（无录音文本）

- `08:50:45` _[系统] 派单：huxinzz05 接管 user 20315279（来源 `zhaohui-zt-planPage-0-5`，年级 7）_
- `14:51:50` _[外呼第 1 通] duration=0s，DB `status=3`（标记"用户拒绝"，但无录音文本，无法区分占线/拒接）_
- `14:51:57` _[外呼第 2 通] 7 秒后重拨，duration=0s，仍 `status=3`，无录音文本_

> **没有第 3 通外呼，没有后续微信触达**。从派单到放弃的窗口仅 **6 小时 1 分钟**。
>
> 之后整个 4-08~5-09 一个月内：DB 无任何 `tutor_call_record`、无 `class_user_wx_chat_msg_stat`、无 `communication_record`。一直到 5 月后 status=1（释放）。
"""
write_case(case6_events, case6_header, os.path.join(BASE, 'case6_完整时间线.md'))


# ============================================================
# Case 7 · user_id=25594769（四年级 / 私域 SOP / fanranranzz01 / 占线+微信单向 / 未成单）
# ============================================================
case7_events = []
case7_events += load_call(os.path.join(BATCH, 'call_25594769_2026-03-23_135920_0s.json'),
                          dt.datetime(2026, 3, 23, 13, 59, 20), '占线 #1')
case7_events += load_call(os.path.join(BATCH, 'call_25594769_2026-03-23_135944_0s.json'),
                          dt.datetime(2026, 3, 23, 13, 59, 44), '占线 #2')
# 第 3 通 18:18:32 无 call_text_url，跳过
case7_events += load_wechat(os.path.join(BATCH, 'batch2_chat_25594769_fanranranzz01_iss620.json'),
                            '1688857067826745', '7881301986932094', label='fanranranzz01')
case7_call = [e for e in case7_events if e['source'] == 'call']
case7_wx = [e for e in case7_events if e['source'] == 'wx']
case7_all = sorted(merge_call_lines(case7_call) + case7_wx, key=lambda x: x['ts'])

case7_header = """# Case 7 · 四年级私域 SOP·销售单向独白 88 条（user_id=25594769）完整时间线

> **画像**：小学四年级学生（实际接电话/接微信的家长未知）。  
> **渠道**：`siyu-qw-sop_0yuan-0-40`（**企微私域 SOP** 0 元体验）—— 来自已存在的微信好友池，但 SOP 自动化触达。  
> **销售**：`fanranranzz01`（凡冉冉）。  
> **结局**：进班 issue 620（2026-03-23 10:20）→ **3 通外呼全部 0 接通**（2 通用户手机占线，1 通无录音）→ 微信触达持续 46 天 88 条但用户**只回了 3 条**（其中 2 条系统加好友提示）→ status=1 已释放。  
>
> **数据规模**：3 通外呼 0 有效通话 + 1 个微信会话 **88 条**（销售 ≥56 / 用户 = 3）。  
>
> ⚠️ **关键**：这是「**销售自言自语 46 天**」的典型样本。88 条消息里销售群发式硬推 200 元/400 元代金券、限时抢购、家长会、抢购倒计时——用户**始终没有任何业务回应**。AI 销售复盘维度：① 何时该停止单向推送 ② SOP 自动化推送的有效边界。

"""
write_case(case7_all, case7_header, os.path.join(BASE, 'case7_完整时间线.md'))


# ============================================================
# Case 8 · user_id=53167626（七年级 / 站内 AI 外呼弹窗 / yangjiaozz02 / 占线+微信单向 / 未成单）
# ============================================================
case8_events = []
case8_events += load_call(os.path.join(BATCH, 'call_53167626_2026-04-01_133358_0s.json'),
                          dt.datetime(2026, 4, 1, 13, 33, 58), '占线 #1')
case8_events += load_call(os.path.join(BATCH, 'call_53167626_2026-04-01_133515_0s.json'),
                          dt.datetime(2026, 4, 1, 13, 35, 15), '占线 #2')
case8_events += load_call(os.path.join(BATCH, 'call_53167626_2026-04-01_133604_0s.json'),
                          dt.datetime(2026, 4, 1, 13, 36, 4), '占线 #3')
case8_events += load_call(os.path.join(BATCH, 'call_53167626_2026-04-01_185714_0s.json'),
                          dt.datetime(2026, 4, 1, 18, 57, 14), '占线 #4')
case8_events += load_call(os.path.join(BATCH, 'call_53167626_2026-04-01_185729_0s.json'),
                          dt.datetime(2026, 4, 1, 18, 57, 29), '占线 #5')
case8_events += load_wechat(os.path.join(BATCH, 'batch2_chat_53167626_yangjiaozz02_iss620.json'),
                            '1688858223671776', '7881300017973370', label='yangjiaozz02')
case8_call = [e for e in case8_events if e['source'] == 'call']
case8_wx = [e for e in case8_events if e['source'] == 'wx']
case8_all = sorted(merge_call_lines(case8_call) + case8_wx, key=lambda x: x['ts'])

case8_header = """# Case 8 · 初一站内 AI 外呼弹窗·5 次连环占线（user_id=53167626）完整时间线

> **画像**：七年级（初一）学生，凌晨进班（00:11 系统派单时间）。  
> **渠道**：`zhaohui-app_act-aicall-0yuan-tanchuang`（**站内 AI 外呼弹窗** 0 元）—— 用户在 APP 内点了弹窗，被 AI 外呼留资后进入销售跟进。  
> **销售**：`yangjiaozz02`（杨娇）。  
> **结局**：进班 issue 620（2026-04-01 01:11）→ **5 通外呼全部"您拨打的电话正在通话中"**（不是拒接、是真·号码占线）→ 微信触达持续 34 天 71 条但用户**仅回 1 条**（首次加微的系统提示）→ status=1 已释放。  
>
> **数据规模**：5 通外呼全占线 + 1 个微信会话 **71 条**（销售 ≥20 / 用户 = 1）。  
>
> ⚠️ **关键**：① **5 通连环占线**说明用户的电话号码这天确实在通话中，但销售集中在 13:33 和 18:57 两个 15 秒以内的密集拨打窗口里——AI 外呼的间隔策略（15 秒/3 通 + 1.5 小时后 15 秒/2 通）是无效的，应该跨日重试。② DB 里 `status=3`「用户拒绝」**口径错误**，实际是占线，是数据治理问题。③ 微信 71 条全销售方推送，无任何用户回应。

"""
write_case(case8_all, case8_header, os.path.join(BASE, 'case8_完整时间线.md'))


# ============================================================
# Case 9 · user_id=111248866（六年级 / 直投 zt-planPage / niuboyuanzz / 当天成单 ¥1399）
# ============================================================
case9_events = []
# 销售期通话：首通 410s = 6.8min
case9_events += load_call(os.path.join(BATCH, 'call_111248866_2026-03-08_123026_410s.json'),
                          dt.datetime(2026, 3, 8, 12, 30, 26), 'niuboyuanzz 首通')
# 销售期微信
case9_events += load_wechat(os.path.join(BATCH, 'batch2_chat_111248866_niuboyuanzz_iss620.json'),
                            '1688855421638985', '7881303161056596', label='niuboyuanzz')
# 助理期微信（两个老师串）
case9_events += load_wechat(os.path.join(BATCH, 'batch2_chat_111248866_chengzinuo_iss60_a.json'),
                            '1688858049788884', '7881303161056596', label='chengzinuo（助理 A）')
case9_events += load_wechat(os.path.join(BATCH, 'batch2_chat_111248866_chengzinuo_iss60_b.json'),
                            '1688858421799034', '7881303161056596', label='chengzinuo（助理 B）')
case9_call = [e for e in case9_events if e['source'] == 'call']
case9_wx = [e for e in case9_events if e['source'] == 'wx']
case9_all = sorted(merge_call_lines(case9_call) + case9_wx, key=lambda x: x['ts'])

case9_header = """# Case 9 · 六年级·当天进班·当天首通 6.8min·当晚成单 ¥1399（user_id=111248866）完整时间线

> **画像**：六年级（小升初）学生「聪聪」，妈妈接电话。  
> **渠道**：`zhaohui-zt-planPage-0-1`（直投留资·学习计划页 0 元）—— **与 case3 同渠道族（zt-planPage 系列）**。  
> **销售**：销售期 `niuboyuanzz`（牛博源） → 助理期 `chengzinuo`（程子诺）。  
> **结局**：**进班当天 8.5 小时闭环成单**：
> | 时间 | 事件 |
> |---|---|
> | 2026-03-08 07:19 | 进班 issue 620 |
> | 2026-03-08 12:30 | **首通 6.8 分钟有效通话** |
> | 2026-03-08 20:53 | **完成支付 ¥1399 体验课转化**（leads_transform_record，transform_type=1，未退费 status=1）|
> | 2026-03-08 23:10 | 进班 issue 60（助理期 chengzinuo 接班）|
>
> 后续助理期跨 4-07~5-09 持续 2 个月伴学陪跑，4 通通话累计 5.8 分钟（首通 5.8min + 后续 36s/35s 短确认）。
>
> **数据规模**：销售期 = 1 通 6.8min + 125 条微信；助理期 = 4 通 + 254 条微信。  
>
> ⚠️ **核心反差锚点**（vs case3）：
> | 维度 | Case 9（本 case） | Case 3（已知成单参照） |
> |---|---|---|
> | 渠道 | zt-planPage-0-1（直投） | 同 zt-planPage 系列 |
> | 销售 | niuboyuanzz | huxinzz05 |
> | 首通时长 | 6.8 min | 9.5 min |
> | 成单关键通话 | **首通即成单**（无第二通） | 首通 9.5min + 长聊 26.8min |
> | 闭环时长 | **当天 8.5 小时** | 跨 7 天（4-11 首通 → 4-18 长聊成单） |
> | 转化金额 | ¥1399 | ¥1049 |
>
> Case 9 是**比 case3 更"短平快"的 1A 成单路径**——AI 销售首诊就能闭环。

"""
write_case(case9_all, case9_header, os.path.join(BASE, 'case9_完整时间线.md'))


# ============================================================
# Case 10 · user_id=133236776（初二 / VIP 页咨询 / huxinzz05 / 12s 短拒 / 仍跟进未成单）
# ============================================================
case10_events = []
case10_events += load_call(os.path.join(BATCH, 'call_133236776_2026-04-13_140443_0s.json'),
                           dt.datetime(2026, 4, 13, 14, 4, 43), '占线 #2（重拨）')
case10_call = [e for e in case10_events if e['source'] == 'call']
case10_all = sorted(merge_call_lines(case10_call), key=lambda x: x['ts'])

case10_header = """# Case 10 · 初二 VIP 页咨询·12 秒接通秒挂（user_id=133236776）完整时间线

> **画像**：八年级（初二）学生，VIP 页主动咨询入口留资。  
> **渠道**：`zhaohui-nature-vipPageConsult-0-1`（**VIP 页咨询** 0 元体验，自然流量）—— 与前面几个 case 的"被动派单"不同，这是用户**主动来询**的流量。  
> **销售**：`huxinzz05`（贺心·**同 case3 成单 + case6 0 接通 的销售**）。  
> **结局**：进班 issue 620（2026-04-13 07:47）→ **首拨 12 秒接通即被秒挂**（DB `status=1` 成功，duration=12s）→ 35 秒后立即重拨遇用户占线 → 25 秒后再拨无录音 → status=0 **仍有效**（销售未放弃）。  
>
> **数据规模**：3 通外呼（1 通 12s 接通+秒挂，1 通占线，1 通无文本）+ **0 个微信会话**（DB `class_user_wx_chat_msg_stat` 无任何 vid 映射，未成功加微）。  
>
> ⚠️ **关键**：① 这个 case **接通了 12 秒**——是 5 个未转化 case 里**唯一接通真人的样本**，比起 case6/7/8 的"0 接通"，多出一个"接通即拒"的反应数据，可能能听到第一句拒绝话术（call_text_url 此通为 null，需查 audio_url）；② 同销售 huxinzz05 的 3 个 case 大反差：case3（同渠道 zt 系成单 ¥1049）vs case6（直投 0 接通弃单）vs case10（VIP 咨询 12s 短拒）—— **同一个销售技能对不同流量结果完全不同**，关键变量在线索本身/上游流量质量。

## 2026-04-13 Monday · 进班当天与销售跟进窗口


### 📞 外呼

- `07:47:09` _[系统] 派单：huxinzz05 接管 user 133236776（来源 `zhaohui-nature-vipPageConsult-0-1`，年级 8 / 初二）_
- `14:04:08` _[外呼第 1 通] duration=**12s**，DB `status=1`（接通成功），call_text_url=null，audio_url 有 mp3（需听音频才能知道用户说了什么）_
- `14:04:43` _[外呼第 2 通] 35 秒后立即重拨，duration=0s，录音文本只有一句_"您好。您拨打的电话正在通话中。"_——说明用户挂掉电话后号码立即变占线状态。_
- `14:05:08` _[外呼第 3 通] 又 25 秒后再拨，duration=0s，无录音文本_

> 之后整个 4-13 ~ 5-12 一个月内：DB 无任何后续通话，无微信记录。但 status=0 表示销售线索池里仍标"有效"，未释放。
>
> **疑点**：4-13 13:36 有 1 条 `communication_record`（communication_type=54，status=1），可能是销售在通话前给一次系统化触达（如发短信/AI 触达）。type=54 不在标准 1首触/2催习/3通知 字典里，需查工作台 communication API 确认具体动作。
"""
write_case(case10_all, case10_header, os.path.join(BASE, 'case10_完整时间线.md'))

print("\nDONE: case6-case10 时间线已生成至", BASE)
