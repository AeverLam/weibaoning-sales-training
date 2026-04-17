#!/bin/bash
# 部署修复后的维宝宁销售培训机器人到 Render

echo "🚀 开始部署修复版本..."

# 检查必要的环境变量
if [ -z "$RENDER_SERVICE_ID" ]; then
    echo "⚠️  请设置 RENDER_SERVICE_ID 环境变量"
    echo "示例: export RENDER_SERVICE_ID=srv-xxxxxxxx"
    exit 1
fi

# 提交代码到 GitHub
echo "📦 提交代码更改..."
git add render_app_final.py
git commit -m "修复重复消息问题：
- 添加消息ID持久化去重（24小时缓存）
- 添加内容哈希去重（60秒内不重复发送相同内容）
- 添加异常保护，防止后台线程崩溃
- 双重检查机制（内存+文件）"

echo "📤 推送到 GitHub..."
git push origin main

# 触发 Render 重新部署
echo "🔄 触发 Render 重新部署..."
curl -X POST \
  "https://api.render.com/v1/services/$RENDER_SERVICE_ID/deploys" \
  -H "Authorization: Bearer $RENDER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"clearCache": true}'

echo ""
echo "✅ 部署已触发！"
echo "请前往 Render Dashboard 查看部署状态:"
echo "https://dashboard.render.com/web/$RENDER_SERVICE_ID"
