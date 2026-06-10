"""
Step 2: 解析反馈记录，做分层抽样
- 输入：af898f08-08c2-4422-bdf5-5a0627f17ac4.txt (3320 条 type25/69 记录)
- 抽样口径：
  · 按用户去重（每用户取最早一条反馈记录作为反馈锚点，type25 优先于 type69）
  · 按销售 tutor_ldap 多样化（每老师最多 2 人）
  · 留待补：转化状态（后续 step3 拉 Chrome 后补）
- 输出：sampled_users.json
"""
import json
import csv
import random
from pathlib import Path
from collections import defaultdict

BASE = Path(__file__).parent
RAW = Path("/Users/jiwenyue/.cursor/projects/Users-jiwenyue-Abigial/agent-tools")
COMM_FILE = RAW / "af898f08-08c2-4422-bdf5-5a0627f17ac4.txt"

with open(COMM_FILE) as f:
    data = json.load(f)
rows = data["data"]["rows"]
print(f"原始反馈记录条数: {len(rows)}")

# columns: user_id, tutor_ldap, communication_type, status, comm_ts
user_anchor = {}  # user_id -> (tutor_ldap, type, status, ts)
for r in rows:
    uid, tutor, ct, st, ts = r
    if st != 1:  # 只保留沟通成功
        continue
    cur = user_anchor.get(uid)
    if cur is None:
        user_anchor[uid] = (tutor, ct, st, ts)
        continue
    # 同用户多条：优先 type25，时间最早
    cur_tutor, cur_ct, cur_st, cur_ts = cur
    if ct == 25 and cur_ct != 25:
        user_anchor[uid] = (tutor, ct, st, ts)
    elif ct == cur_ct and ts < cur_ts:
        user_anchor[uid] = (tutor, ct, st, ts)

print(f"去重后反馈用户数（沟通成功）: {len(user_anchor)}")

# 反馈类型分布
type_dist = defaultdict(int)
for v in user_anchor.values():
    type_dist[v[1]] += 1
print(f"反馈类型分布: {dict(type_dist)}")

# 销售分布
tutor_dist = defaultdict(int)
for v in user_anchor.values():
    tutor_dist[v[0]] += 1
print(f"涉及销售老师数: {len(tutor_dist)}")
print(f"销售人均反馈用户数: {len(user_anchor)/max(len(tutor_dist),1):.1f}")

# === 分层抽样 ===
# 目标：20 通
# 原则：
#  - 25/69 按真实占比抽（25 约 84%，69 约 16%） → 25 抽 17 个，69 抽 3 个
#  - 同一老师最多 2 人，尽量分散
#  - 反馈时间错开（早/中/晚 各几个）

# 按 type 分桶
by_type = defaultdict(list)
for uid, v in user_anchor.items():
    by_type[v[1]].append((uid, *v))

random.seed(42)

target_25 = 19  # 多抽 2 个，预留替换失败 case
target_69 = 4

# 按 tutor 多样化抽：先按时间分桶，每桶随机抽
def stratified_pick(pool, n, tutor_cap=2):
    pool = sorted(pool, key=lambda x: x[4])  # 按 ts
    chunk_size = max(1, len(pool) // n)
    chunks = [pool[i*chunk_size:(i+1)*chunk_size] for i in range(n)]
    if len(chunks) < n:
        chunks.append(pool[n*chunk_size:])
    picked = []
    tutor_cnt = defaultdict(int)
    for chunk in chunks:
        random.shuffle(chunk)
        for item in chunk:
            tutor = item[1]
            if tutor_cnt[tutor] >= tutor_cap:
                continue
            picked.append(item)
            tutor_cnt[tutor] += 1
            break
    return picked

picked_25 = stratified_pick(by_type[25], target_25, tutor_cap=2)
picked_69 = stratified_pick(by_type[69], target_69, tutor_cap=2)
print(f"抽样: type25 {len(picked_25)} 人 / type69 {len(picked_69)} 人")

# 整合输出
sampled = []
for item in picked_25 + picked_69:
    uid, tutor, ct, st, ts = item
    sampled.append({
        "user_id": uid,
        "tutor_ldap": tutor,
        "comm_type": ct,
        "comm_status": st,
        "comm_ts": ts,
    })

out = BASE / "sampled_users.json"
with open(out, "w") as f:
    json.dump(sampled, f, ensure_ascii=False, indent=2)
print(f"已写入: {out}  ({len(sampled)} 用户)")

# 也写 user_ids 便于后续查电话
ids_out = BASE / "sampled_user_ids.txt"
with open(ids_out, "w") as f:
    for s in sampled:
        f.write(f"{s['user_id']}\n")
print(f"user_id 列表已写入: {ids_out}")

# 列出涉及销售（去重）
tutors = sorted(set(s["tutor_ldap"] for s in sampled))
print(f"涉及销售: {len(tutors)} 人")
for t in tutors:
    cnt = sum(1 for s in sampled if s["tutor_ldap"] == t)
    print(f"  {t}: {cnt}")
