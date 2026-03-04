#!/bin/bash
# 工作日 10:40 自动提醒今日待办

TODOS_FILE="$HOME/cursorProjects/personal/work/todos.md"

# 只在工作日运行（1=周一 ... 5=周五）
DOW=$(date +%u)
if [ "$DOW" -gt 5 ]; then
  exit 0
fi

if [ ! -f "$TODOS_FILE" ]; then
  osascript -e 'display dialog "todos.md 文件不存在" with title "⚠️ 工作提醒" buttons {"好"} default button "好"'
  exit 1
fi

# 解析紧急重要区块中的任务
IN_URGENT=0
COUNT=0
TITLE=""
DEADLINE=""
TODO_NOTE=""
STATUS=""
OUTPUT=""

flush_task() {
  if [ -n "$TITLE" ]; then
    COUNT=$((COUNT + 1))
    LINE="${COUNT}. ${TITLE}"
    [ -n "$STATUS" ] && LINE="${LINE}  ${STATUS}"
    [ -n "$DEADLINE" ] && LINE="${LINE}  验收${DEADLINE}"
    OUTPUT="${OUTPUT}${LINE}\n"
    [ -n "$TODO_NOTE" ] && OUTPUT="${OUTPUT}    → ${TODO_NOTE}\n"
  fi
  TITLE=""
  DEADLINE=""
  TODO_NOTE=""
  STATUS=""
}

while IFS= read -r line; do
  if echo "$line" | grep -q "^## 紧急重要"; then
    IN_URGENT=1
    continue
  fi
  if [ "$IN_URGENT" -eq 1 ] && echo "$line" | grep -q "^## "; then
    flush_task
    break
  fi
  if [ "$IN_URGENT" -eq 1 ] && echo "$line" | grep -q "^### "; then
    flush_task
    TITLE=$(echo "$line" | sed 's/^### [0-9]*\. //')
  fi
  if [ "$IN_URGENT" -eq 1 ] && echo "$line" | grep -q "^\- \*\*验收\*\*"; then
    DEADLINE=$(echo "$line" | sed 's/.*：//')
  fi
  if [ "$IN_URGENT" -eq 1 ] && echo "$line" | grep -q "^\- \*\*TODO\*\*"; then
    TODO_NOTE=$(echo "$line" | sed 's/.*：//')
  fi
  if [ "$IN_URGENT" -eq 1 ] && echo "$line" | grep -q "^\- \*\*状态\*\*"; then
    STATUS=$(echo "$line" | sed 's/.*：//')
  fi
done < "$TODOS_FILE"
flush_task

TODAY=$(date '+%m月%d日 %A' | sed \
  -e 's/Monday/周一/' -e 's/Tuesday/周二/' -e 's/Wednesday/周三/' \
  -e 's/Thursday/周四/' -e 's/Friday/周五/')

if [ "$COUNT" -eq 0 ]; then
  BODY="暂无紧急待办，保持节奏 💪"
else
  BODY=$(printf '%b' "$OUTPUT")
fi

# AppleScript 弹窗：展示待办，可一键打开文件；5 分钟无操作自动关闭
RESULT=$(osascript <<EOF
set theMessage to "📋 今日待办 · ${TODAY}\n共 ${COUNT} 项紧急任务\n\n${BODY}"
set theResult to display dialog theMessage with title "工作日报提醒" buttons {"打开待办文件", "知道了"} default button "知道了" giving up after 300
if button returned of theResult is "打开待办文件" then
  do shell script "open '${TODOS_FILE}'"
end if
EOF
)

# 同时输出到日志
echo "=== 工作日报提醒 ${TODAY} ==="
printf '%b' "$OUTPUT"
echo "=========================="
