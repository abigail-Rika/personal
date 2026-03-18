#!/bin/bash
# 备份所有 Cursor Agent 聊天记录到 personal 空间
# 用法: bash ~/cursorProjects/personal/scripts/backup-chats.sh

BACKUP_DIR="$HOME/cursorProjects/personal/backups/agent-chats/$(date +%Y-%m-%d)"
SOURCE_DIR="$HOME/.cursor/projects"

mkdir -p "$BACKUP_DIR"

count=0
for dir in "$SOURCE_DIR"/*/agent-transcripts; do
    [ -d "$dir" ] || continue
    workspace=$(basename "$(dirname "$dir")")
    target="$BACKUP_DIR/$workspace"
    mkdir -p "$target"
    cp -r "$dir"/* "$target/" 2>/dev/null
    n=$(ls "$target" 2>/dev/null | wc -l | tr -d ' ')
    count=$((count + n))
    echo "  $workspace: $n 个对话"
done

echo ""
echo "✅ 备份完成: $count 个对话 → $BACKUP_DIR"
