---
description: "用 osascript 控制 Chrome 拉内部销售工作台 API（聊天记录 100KB+），3 种方案失败（title 6KB 上限/Blob 用户手势/分块转义），URL hash + base64 最终成功"
---

# 通过 Chrome 调内部 API 回传大量 JSON 数据——4 种方案 3 次失败 1 次成功

日期: 2026-05-11
角色: AI工程

## 背景

需要从公司内部销售工作台拉取真实用户的微信聊天记录（76~171 条/会话）作为 AI 销售对话脚本的参考素材。这些 API 必须带销售工作台的登录态才能调通，不能用 curl。

可选方案：
1. 让用户在浏览器里手动操作下载 → 慢、不可批量
2. 用 playwright MCP → 当时没有这个 MCP，且开新窗口会丢登录态
3. 让用户在浏览器里执行 JavaScript，fetch 到数据后回传给 shell → 选这条

## 经过：踩了 3 个坑，第 4 种方案才跑通

### 方案 1（失败）：`document.title` 直接回传

最直接的思路：

```javascript
fetch(API).then(r=>r.json()).then(d=>{
  document.title = JSON.stringify(d);
});
```

然后 osascript 读 `title of foundTab`。

**问题**：Chrome 的 `document.title` 实际有 **~6KB 字符上限**，超过会被截断。171 条聊天记录序列化后 ~120KB，直接被砍。

### 方案 2（失败）：Blob + 触发下载

```javascript
const blob = new Blob([JSON.stringify(d)], {type:'application/json'});
const a = document.createElement('a');
a.href = URL.createObjectURL(blob);
a.download = 'data.json';
a.click();
```

**问题**：Chrome 强制要求 `a.click()` 必须由"用户手势"触发，AppleScript 注入的 JS 不算用户手势。下载没反应或者文件 0 字节。

### 方案 3（失败）：分块写 `document.title`

把数据切成 4KB 块，循环写 title，每次读一块：

```javascript
window.__chunks = chunks;
window.__idx = 0;
// shell 端循环：调 osascript 让 JS 取下一块写入 title
```

**问题**：
- osascript 循环里 shell 转义复杂，频繁失败
- JSON 里的转义字符（`\n`、`\"`）在跨 osascript ↔ shell ↔ Python 多层转码时被反复破坏，最终 JSON 解析失败

### 方案 4（成功）：URL hash 大法

突然意识到——浏览器的 URL hash（`#` 后面的内容）**没有大小限制、不触发页面刷新、不发请求**，可以塞任意大数据。

```javascript
(async()=>{
  // ... 拉数据，全部塞到 all 数组
  const b64 = btoa(unescape(encodeURIComponent(JSON.stringify(all))));
  history.replaceState(null, '', '#DATA:' + b64);
  document.title = 'READY:' + all.length;  // title 只用来给 osascript 一个信号
})();
```

shell 端：

```bash
# osascript 读 URL（不是 title）
osascript ... return URL of foundTab > /tmp/url.txt

# 从 # 后面切出 base64
B64=$(perl -ne 's/^.*#DATA://; s/\s+//g; print' /tmp/url.txt)

# 解码
echo "$B64" | base64 -d > data.json
```

**实测**：单次拉 76~171 条聊天记录（base64 后约 50~140KB），URL hash 完整无损。

## 关键收获

1. **`document.title` 不是无限大**：实测约 6KB 上限。任何大于这个的数据回传方案都会被截断。

2. **AppleScript 注入的 JS 不算用户手势**：所有依赖"用户手势"的 Web API（下载触发、剪贴板写入旧版 API、全屏请求等）都不能用。

3. **URL hash 是浏览器里被忽视的大容量字段**：
   - 不发请求、不刷新页面
   - 现代浏览器没有明确上限（实测 100KB+ 完全 OK）
   - `osascript` 取 `URL of foundTab` 比取 title 一样简单
   - base64 编码后没有 JSON 转义字符的痛苦

4. **AppleScript 关键字会污染 JS heredoc**：当 JS 里包含 `async`、`as`、`of` 等 AppleScript 关键字时，即使在字符串字面量内，osascript 也会报语法错。**解决：把 JS 写到独立 `.js` 文件，AppleScript 用 `cat $JS_FILE` 注入到 `set jsCode to "..."` 里**。

5. **跨工具数据传输优先用 base64**：避免 JSON 转义字符在 osascript → shell → Python 多层转码中被破坏。base64 全是 ASCII alphanum，没有任何工具会"聪明地"转义它。

## Triggers

- "Chrome osascript 调内部 API"
- "登录态 API 数据回传"
- "document.title 上限"
- "AppleScript JavaScript heredoc 报错"
- "URL hash 数据传输"
- "shell 调浏览器拉数据"
- "playwright 替代方案"
