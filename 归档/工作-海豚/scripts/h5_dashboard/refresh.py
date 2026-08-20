#!/usr/bin/env python3
"""H5 抽奖看板自动刷新脚本。

每次运行：
1. 调用 bigdata-mcp HTTP 接口跑 4 个 SQL（6/06 各 URL 指标 / 6/06 停留 P50 /
   6/06 已登录用户聚合 / 6/01~6/06 累计指标）
2. 跑一次完整用户明细 SQL，下载 CSV 覆盖到 personal/work/analysis/...
3. 把 canvases/h5-lottery-tracking.canvas.tsx 里的 AUTO_REFRESH_BLOCK 替换为最新数据

会跳过执行：当前时间 > TODAY_CUTOFF_LOCAL，避免 launchd 一直跑。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

# ----- 配置 -----
MCP_ENDPOINT = "https://bigdata-mcp.zhenguanyu.com/mcp"
MCP_TOKEN = "JeCvfORisCkwWavEKXSfmEsVmEKHdRGv"
TARGET_DT = "2026-06-06"
RANGE_START_DT = "2026-06-01"
CANVAS_PATH = Path(
    "/Users/jiwenyue/.cursor/projects/Users-jiwenyue-Abigial/canvases/h5-lottery-tracking.canvas.tsx"
)
CSV_PATH = Path(
    "/Users/jiwenyue/Abigial/personal/work/analysis/h5_lottery_users/h5_lottery_logged_in_users_20260606.csv"
)
LOG_DIR = Path("/Users/jiwenyue/Abigial/personal/work/scripts/h5_dashboard/logs")
# 截止时间：到这个时间点之后脚本自我退出（launchd 即便继续触发也无副作用）
TODAY_CUTOFF_LOCAL = datetime(2026, 6, 6, 23, 0, 0)

# 企微机器人推送
WECOM_WEBHOOK_KEY = "8c7b2135-07e0-44df-bddf-fcd5a4f905ce"
WECOM_BASE = "https://qyapi.weixin.qq.com/cgi-bin/webhook"

BLOCK_START = "// ===== AUTO_REFRESH_BLOCK_START ====="
BLOCK_END = "// ===== AUTO_REFRESH_BLOCK_END ====="


# ----- MCP 调用 -----
def mcp_call(name: str, arguments: dict, req_id: int = 1) -> dict:
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        MCP_ENDPOINT,
        data=body,
        headers={
            "Authorization": f"Bearer {MCP_TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        raw = resp.read().decode("utf-8")
    payload = json.loads(raw)
    if "error" in payload:
        raise RuntimeError(f"MCP error: {payload['error']}")
    text = payload["result"]["content"][0]["text"]
    return json.loads(text)


def submit_async(sql: str) -> int:
    """提交 SQL，立即返回 queryId（不等结果）。"""
    resp = mcp_call(
        "adhoc_submitQuery",
        {
            "catalog": "hive_f04",
            "database": "dw_ori",
            "engine": "Trino",
            "timeoutSeconds": 0,
            "sql": sql,
        },
    )
    if resp.get("status") != "SUCCESS":
        raise RuntimeError(f"Submit failed: {resp.get('message')}")
    return int(resp["data"])


def wait_result(query_id: int, timeout_s: int = 300) -> dict:
    resp = mcp_call(
        "adhoc_getQueryResult",
        {"queryId": query_id, "timeoutSeconds": timeout_s},
    )
    if resp.get("status") not in ("SUCCESS",):
        raise RuntimeError(f"getQueryResult failed: {resp.get('message')}")
    data = resp["data"]
    if data.get("status") not in ("成功",):
        raise RuntimeError(f"Query {query_id} failed: {data.get('message')}")
    return data


def submit_query(sql: str, timeout_s: int = 300) -> dict:
    qid = submit_async(sql)
    return wait_result(qid, timeout_s=timeout_s)


def submit_query_and_id(sql: str, timeout_s: int = 300) -> tuple[dict, int]:
    qid = submit_async(sql)
    return wait_result(qid, timeout_s=timeout_s), qid


# ----- 企微推送 -----
def wecom_upload_file(csv_path: Path) -> str:
    """上传文件到企微，返回 media_id（有效期 3 天）。"""
    url = f"{WECOM_BASE}/upload_media?key={WECOM_WEBHOOK_KEY}&type=file"
    result = subprocess.run(
        [
            "curl",
            "-sS",
            "-X",
            "POST",
            url,
            "-F",
            f"media=@{csv_path};filename={csv_path.name};type=text/csv",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"curl upload failed: {result.stderr}")
    resp = json.loads(result.stdout)
    if resp.get("errcode") != 0:
        raise RuntimeError(f"wecom upload failed: {resp}")
    return resp["media_id"]


def wecom_post(payload: dict) -> None:
    url = f"{WECOM_BASE}/send?key={WECOM_WEBHOOK_KEY}"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        resp = json.loads(r.read().decode("utf-8"))
    if resp.get("errcode") != 0:
        raise RuntimeError(f"wecom send failed: {resp}")


def push_to_wecom(today: dict, csv_path) -> None:  # csv_path: Optional[Path]
    rate = (
        today["ctaClickUv"] / today["pageUv"] * 100 if today.get("pageUv") else 0
    )
    dacu_rate = (
        today["usersInDacuPool"] / today["distinctUsers"] * 100
        if today.get("distinctUsers") else 0
    )
    renew_rate = (
        today["usersRenewed"] / today["distinctUsers"] * 100
        if today.get("distinctUsers") else 0
    )
    md = (
        f"## H5 抽奖看板 · {today['asOf']}\n"
        f"<font color=\"comment\">每 10 分钟自动刷新 · 数据来源 ori_aries_new_frog</font>\n\n"
        f"- 页面曝光 UV：**{today['pageUv']:,}**  "
        f"（已登录 {today['pageUvLogged']:,} / 未登录 {today['pageUvAnon']:,}）\n"
        f"- 按钮点击 UV：**{today['ctaClickUv']:,}**  "
        f"· 点击率 <font color=\"info\">{rate:.1f}%</font>\n"
        f"- 中奖弹窗 UV：{today['prizeUv']:,}  "
        f"· 登录曝光 UV：{today['loginUv']:,}\n"
        f"- 停留时长 P50：{today['stayP50']}s\n"
        f"- 已登录独立用户：**{today['distinctUsers']:,}**  "
        f"（绑定助理 {today['usersWithTutor']:,}）\n"
        f"- 命中大促池：<font color=\"warning\">{today['usersInDacuPool']:,}</font> "
        f"({dacu_rate:.1f}%)  "
        f"· 已续费：<font color=\"info\">{today['usersRenewed']:,}</font> "
        f"({renew_rate:.1f}%)\n"
    )
    wecom_post({"msgtype": "markdown", "markdown": {"content": md}})
    if csv_path and csv_path.exists():
        media_id = wecom_upload_file(csv_path)
        wecom_post({"msgtype": "file", "file": {"media_id": media_id}})


def get_download_url(query_id: int) -> str:
    resp = mcp_call(
        "adhoc_getQueryDownloadUrl", {"queryId": query_id, "convertToExcel": False}
    )
    if resp.get("status") != "SUCCESS":
        raise RuntimeError(f"download url failed: {resp.get('message')}")
    url = resp.get("data")
    if not isinstance(url, str) or not url.startswith("http"):
        raise RuntimeError(f"unexpected download response: {resp!r}")
    return url


# ----- SQL -----
SQL_TODAY_METRICS = f"""
SELECT url,
       COUNT(*) AS pv,
       COUNT(DISTINCT deviceid) AS uv_all,
       COUNT(DISTINCT CASE WHEN userid > 0 THEN deviceid END) AS uv_logged
FROM hive_f04.dw_ori.ori_aries_new_frog
WHERE dt = '{TARGET_DT}' AND url LIKE '%h5LotteryPage%'
GROUP BY url
""".strip()

SQL_STAY = f"""
WITH stay AS (
  SELECT deviceid,
         MAX(TRY_CAST(element_at(customextend, 'tick_count') AS BIGINT)) * 5 AS stay_seconds
  FROM hive_f04.dw_ori.ori_aries_new_frog
  WHERE dt = '{TARGET_DT}'
    AND url = '/event/h5LotteryPage/heartbeat'
    AND element_at(customextend, 'tick_count') IS NOT NULL
  GROUP BY deviceid
)
SELECT APPROX_PERCENTILE(CAST(stay_seconds AS DOUBLE), 0.5) AS p50_s,
       COUNT(*) AS uv
FROM stay
""".strip()

SQL_USERS_AGG = f"""
WITH visited AS (
  SELECT userid
  FROM hive_f04.dw_ori.ori_aries_new_frog
  WHERE dt = '{TARGET_DT}'
    AND url = '/expose/h5LotteryPage/enter'
    AND userid > 0
  GROUP BY userid
),
tu AS (
  SELECT user_id, tutor_ldap
  FROM hive_f04.aries.dwd_aries_issue_tutor_user_relation_record_da
  WHERE dt = '{TARGET_DT}' AND final_status = 0
),
dacu AS (
  SELECT DISTINCT cast(user_id AS bigint) AS user_id
  FROM hive_f04.temp.dacu_pool_202606
),
renew AS (
  SELECT DISTINCT user_id
  FROM jdbc_aries_tutor_user_mysql_pipe_reader_tutoruser510410_tutoruser510410.aries_tutor_user.leads_transform_record
  WHERE dbctime >= timestamp '{RANGE_START_DT} 00:00:00'
    AND dbctime <  timestamp '2026-06-16 00:00:00'
    AND transform_type = 3
)
SELECT COUNT(*) AS distinct_users,
       COUNT(tu.tutor_ldap) AS users_with_tutor,
       COUNT(dacu.user_id) AS users_in_dacu_pool,
       COUNT(renew.user_id) AS users_renewed
FROM visited v
LEFT JOIN tu   ON v.userid = tu.user_id
LEFT JOIN dacu ON v.userid = dacu.user_id
LEFT JOIN renew ON v.userid = renew.user_id
""".strip()

SQL_RANGE_TOTAL = f"""
SELECT url,
       COUNT(*) AS pv,
       COUNT(DISTINCT deviceid) AS uv_all
FROM hive_f04.dw_ori.ori_aries_new_frog
WHERE dt BETWEEN '{RANGE_START_DT}' AND '{TARGET_DT}'
  AND url LIKE '%h5LotteryPage%'
GROUP BY url
""".strip()

SQL_EXPORT_DETAIL = f"""
WITH visited AS (
  SELECT userid,
         MAX(deviceid) AS deviceid,
         COUNT(*) AS pv,
         MIN(receivetime) AS first_ts,
         MAX(receivetime) AS last_ts
  FROM hive_f04.dw_ori.ori_aries_new_frog
  WHERE dt = '{TARGET_DT}'
    AND url = '/expose/h5LotteryPage/enter'
    AND userid > 0
  GROUP BY userid
),
tu AS (
  SELECT user_id, tutor_ldap
  FROM hive_f04.aries.dwd_aries_issue_tutor_user_relation_record_da
  WHERE dt = '{TARGET_DT}' AND final_status = 0
),
td AS (
  SELECT tutor_ldap, tutor_name, level5_mentor_name, level4_mentor_name
  FROM hive_f04.aries.dwd_aries_tutor_department_da_new
  WHERE dt = '{TARGET_DT}'
),
dacu AS (
  SELECT DISTINCT cast(user_id AS bigint) AS user_id
  FROM hive_f04.temp.dacu_pool_202606
),
renew AS (
  SELECT DISTINCT user_id
  FROM jdbc_aries_tutor_user_mysql_pipe_reader_tutoruser510410_tutoruser510410.aries_tutor_user.leads_transform_record
  WHERE dbctime >= timestamp '{RANGE_START_DT} 00:00:00'
    AND dbctime <  timestamp '2026-06-16 00:00:00'
    AND transform_type = 3
)
SELECT v.userid,
       v.deviceid,
       v.pv,
       format_datetime(from_unixtime(v.first_ts / 1000), 'yyyy-MM-dd HH:mm:ss') AS first_seen,
       format_datetime(from_unixtime(v.last_ts / 1000), 'yyyy-MM-dd HH:mm:ss') AS last_seen,
       tu.tutor_ldap,
       td.tutor_name,
       td.level5_mentor_name,
       td.level4_mentor_name,
       CASE WHEN dacu.user_id IS NOT NULL  THEN 'Y' ELSE 'N' END AS in_dacu_pool,
       CASE WHEN renew.user_id IS NOT NULL THEN 'Y' ELSE 'N' END AS has_renewed
FROM visited v
LEFT JOIN tu    ON v.userid = tu.user_id
LEFT JOIN td    ON tu.tutor_ldap = td.tutor_ldap
LEFT JOIN dacu  ON v.userid = dacu.user_id
LEFT JOIN renew ON v.userid = renew.user_id
ORDER BY v.pv DESC, v.userid
""".strip()


# ----- 主流程 -----
def rows_by_url(data: dict) -> dict[str, dict]:
    cols = data["columnNames"]
    out: dict[str, dict] = {}
    for row in data["rows"]:
        rec = dict(zip(cols, row))
        url = rec["url"]
        out[url] = {k: rec[k] for k in rec if k != "url"}
    return out


def main() -> int:
    now = datetime.now()
    if now > TODAY_CUTOFF_LOCAL:
        log(f"[{now:%Y-%m-%d %H:%M:%S}] 已过截止时间 {TODAY_CUTOFF_LOCAL}, 跳过执行")
        return 0

    log(f"=== refresh start: {now:%Y-%m-%d %H:%M:%S} ===")

    today_data = submit_query(SQL_TODAY_METRICS, timeout_s=180)
    today_metrics = rows_by_url(today_data)

    stay_data = submit_query(SQL_STAY, timeout_s=180)
    stay_row = stay_data["rows"][0]
    p50_idx = stay_data["columnNames"].index("p50_s")
    stay_p50 = int(round(float(stay_row[p50_idx])))

    users_data = submit_query(SQL_USERS_AGG, timeout_s=300)
    users_row = users_data["rows"][0]
    users_cols = users_data["columnNames"]
    distinct_users = int(users_row[users_cols.index("distinct_users")])
    users_with_tutor = int(users_row[users_cols.index("users_with_tutor")])
    users_in_dacu = int(users_row[users_cols.index("users_in_dacu_pool")])
    users_renewed = int(users_row[users_cols.index("users_renewed")])

    range_data = submit_query(SQL_RANGE_TOTAL, timeout_s=300)
    range_metrics = rows_by_url(range_data)

    def m(url: str, key: str, src: dict[str, dict]) -> int:
        return int(src.get(url, {}).get(key, 0) or 0)

    today = {
        "asOf": now.strftime("%Y-%m-%d %H:%M"),
        "pageUv": m("/expose/h5LotteryPage/enter", "uv_all", today_metrics),
        "pageUvLogged": m("/expose/h5LotteryPage/enter", "uv_logged", today_metrics),
        "pageUvAnon": m("/expose/h5LotteryPage/enter", "uv_all", today_metrics)
        - m("/expose/h5LotteryPage/enter", "uv_logged", today_metrics),
        "pagePv": m("/expose/h5LotteryPage/enter", "pv", today_metrics),
        "ctaExposeUv": m("/expose/h5LotteryPage/bottomButton", "uv_all", today_metrics),
        "ctaClickUv": m("/click/h5LotteryPage/bottomButton", "uv_all", today_metrics),
        "prizeUv": m("/expose/h5LotteryPage/prizePopup", "uv_all", today_metrics),
        "loginUv": m("/expose/h5LotteryPage/login", "uv_all", today_metrics),
        "stayP50": stay_p50,
        "distinctUsers": distinct_users,
        "usersWithTutor": users_with_tutor,
        "usersInDacuPool": users_in_dacu,
        "usersRenewed": users_renewed,
        "exportQueryId": 0,  # 占位，下面跑导出 SQL 后回填
        "totalPageUv": m("/expose/h5LotteryPage/enter", "uv_all", range_metrics),
        "totalPagePv": m("/expose/h5LotteryPage/enter", "pv", range_metrics),
        "totalCtaExposeUv": m(
            "/expose/h5LotteryPage/bottomButton", "uv_all", range_metrics
        ),
        "totalCtaClickUv": m(
            "/click/h5LotteryPage/bottomButton", "uv_all", range_metrics
        ),
        "totalPrizeUv": m("/expose/h5LotteryPage/prizePopup", "uv_all", range_metrics),
        "totalLoginUv": m("/expose/h5LotteryPage/login", "uv_all", range_metrics),
    }

    log(
        f"today metrics: pageUv={today['pageUv']} click={today['ctaClickUv']} "
        f"logged={today['pageUvLogged']} anon={today['pageUvAnon']} "
        f"dacu={today['usersInDacuPool']} renewed={today['usersRenewed']}"
    )

    # 导出 CSV
    csv_ok = False
    try:
        _, qid = submit_query_and_id(SQL_EXPORT_DETAIL, timeout_s=600)
        today["exportQueryId"] = qid
        url = get_download_url(qid)
        CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["curl", "-sSfL", url, "-o", str(CSV_PATH)], check=True, timeout=120
        )
        log(f"CSV refreshed: {CSV_PATH} (queryId={qid})")
        csv_ok = True
    except Exception as e:
        log(f"WARN: 导出 CSV 失败，跳过本次（保留旧文件）：{e}")

    update_canvas_block(today)
    log(f"canvas updated: {CANVAS_PATH}")

    # 推送企微（CSV 失败时只推 markdown）
    try:
        push_to_wecom(today, CSV_PATH if csv_ok else None)
        log("WeCom pushed: markdown + file" if csv_ok else "WeCom pushed: markdown only")
    except Exception as e:
        log(f"WARN: 推送企微失败：{e}")

    return 0


def update_canvas_block(today: dict) -> None:
    src = CANVAS_PATH.read_text(encoding="utf-8")
    new_obj_lines = ["const TODAY = {"]
    for k, v in today.items():
        if isinstance(v, str):
            new_obj_lines.append(f'  {k}: "{v}",')
        else:
            new_obj_lines.append(f"  {k}: {v},")
    new_obj_lines.append("};")
    new_block = "\n".join(
        [
            BLOCK_START,
            "// 由 scripts/refresh_h5_dashboard.py 每 10 分钟自动覆盖，请勿手改。",
            *new_obj_lines,
            BLOCK_END,
        ]
    )
    pattern = re.compile(
        rf"{re.escape(BLOCK_START)}.*?{re.escape(BLOCK_END)}", re.DOTALL
    )
    if not pattern.search(src):
        raise RuntimeError("AUTO_REFRESH_BLOCK 标记未在 canvas 中找到")
    CANVAS_PATH.write_text(pattern.sub(new_block, src), encoding="utf-8")


def log(msg: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    with (LOG_DIR / "refresh.log").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log(f"ERROR: {e}")
        sys.exit(1)
