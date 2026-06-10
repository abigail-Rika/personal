---
description: "通过 osascript 控制 Chrome 调用需要登录态的内部 API，并把大量返回数据（>10KB）无损回传到 shell。用 URL hash + base64 解决 document.title 的 6KB 上限和 Blob 下载的用户手势限制。"
triggers:
  - "Chrome 调内部 API"
  - "登录态 API 取数"
  - "osascript fetch 大数据"
  - "URL hash 数据传输"
  - "siam.zhenguanyu.com 拉数据"
source:
  - "各角色目录/AI工程/经验/2026-05-11-chrome调内部API回传大数据踩坑.md"
---

# 通过 Chrome 调内部 API 拉大数据——URL hash 大法

## 适用场景

需要在 shell 里调用一个**必须带登录态**的内部 API（无法用 curl/playwright 直接访问），且返回的数据**可能超过 6KB**。

## 三步法

### 第 1 步：把 JS 写到独立文件，避免 osascript 关键字污染

```javascript
// /tmp/fetch.js
(async()=>{
  // 1. 拉数据（可分页）
  let cursor = 0;
  let all = [];
  while (true) {
    const r = await fetch(API_URL + '?cursor=' + cursor, {credentials: 'include'});
    const d = await r.json();
    const items = d.items || [];
    all = all.concat(items);
    if (!d.nextCursor || items.length === 0) break;
    cursor = d.nextCursor;
  }

  // 2. base64 编码 + 塞进 URL hash
  const b64 = btoa(unescape(encodeURIComponent(JSON.stringify(all))));
  history.replaceState(null, '', '#DATA:' + b64);

  // 3. title 只用来给 osascript 一个"完成"信号
  document.title = 'READY:' + all.length;
})();
```

**为什么不能写在 osascript heredoc 里**：JS 关键字 `async`、`as`、`of`、`with` 等会和 AppleScript 关键字冲突，即使在字符串字面量里也会报 `syntax error`。

### 第 2 步：用 osascript 注入 JS、等待、读 URL

```bash
JS=$(cat /tmp/fetch.js)
osascript <<AS > /tmp/url.txt 2>&1
tell application "Google Chrome"
  set foundTab to missing value
  repeat with w in windows
    repeat with t in tabs of w
      if URL of t contains "siam.zhenguanyu.com" then
        set foundTab to t
        exit repeat
      end if
    end repeat
  end repeat
  if foundTab is missing value then return "NO_TAB"
  set jsCode to "$JS"
  tell foundTab to execute javascript jsCode
  delay 6
  return URL of foundTab
end tell
AS
```

注意点：
- 用 `repeat ... if URL contains ...` 动态找目标 tab，**不要**写死 `tab 1 of window 1`，用户切换窗口/tab 时会 `Invalid index`
- `delay` 给足时间。分页 API 一页 1 秒，30 页要 30 秒+缓冲
- 返回 `URL of foundTab` 而不是 `title of foundTab`，因为数据塞在 URL hash 里

### 第 3 步：从 URL 切出 base64 解码

```bash
B64=$(perl -ne 's/^.*#DATA://; s/\s+//g; print' /tmp/url.txt | tr -d '\n\r ')
echo "$B64" | base64 -d > data.json
python3 -c "import json; d=json.load(open('data.json')); print(f'OK msgs={len(d)}')"
```

## 前置条件 checklist

- [ ] 用户在 Chrome 里登录了目标内部系统
- [ ] Chrome → View → Developer → **Allow JavaScript from Apple Events** 已勾选
- [ ] osascript 有"控制 Google Chrome"的辅助功能权限
- [ ] 目标 API 支持 `credentials: 'include'` 跨域携带 cookie

## 常见坑 & 排错

| 现象 | 原因 | 修法 |
|---|---|---|
| osascript 报 `syntax error` 在 JS 行号 | JS 关键字撞 AppleScript 保留字 | JS 写到独立文件，shell 变量插值 |
| `401 Unauthorized` | 登录态过期 / 跨域无 cookie | 用户去 Chrome 刷新登录页；fetch 加 `credentials:'include'` |
| 数据截断 / 不完整 | 用 `document.title` 回传超过 6KB | 改用 URL hash |
| base64 解码报 `Invalid character` | URL 里有空格/换行被 osascript 包进来 | `perl 's/\s+//g'` + `tr -d '\n\r '` 清干净 |
| 一次同时跑两个 fetch 数据互相覆盖 | `document.title` 共享 | 串行跑；或用不同 hash 前缀 `#A:` `#B:` |
| `Invalid index` 找不到 tab | 写死 `tab 1 of window 1`，用户切了 | 用 `repeat ... if URL contains` 动态找 |

## 数据规模参考

实测在 macOS Sonoma + Chrome 124：

| 数据量 | 状态 |
|---|---|
| < 6KB | `document.title` 直接传也 OK |
| 6KB ~ 1MB | URL hash + base64，无损 |
| > 1MB | 没测过，可能要分批 |

## 什么时候需要回溯经验

- 第一次接入需要登录态的内部 API
- osascript 报莫名其妙的 syntax error
- Chrome 拉数据被截断
- 想批量从内部工作台扒数据但 playwright/Selenium 走不通

原始踩坑过程见：`各角色目录/AI工程/经验/2026-05-11-chrome调内部API回传大数据踩坑.md`
