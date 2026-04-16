#!/bin/bash
# Render 启动脚本
# 用于启动维宝宁销售话术对练飞书机器人

echo "🚀 启动维宝宁销售话术对练..."

# 检查环境变量
if [ -z "$FEISHU_APP_ID" ]; then
    echo "⚠️ 警告: FEISHU_APP_ID 未设置"
fi

if [ -z "$FEISHU_APP_SECRET" ]; then
    echo "⚠️ 警告: FEISHU_APP_SECRET 未设置"
fi

# 设置默认端口
PORT=${PORT:-5000}

echo "📋 配置信息:"
echo "  - 端口: $PORT"
echo "  - 应用ID: ${FEISHU_APP_ID:-未设置}"
echo "  - 工作目录: $(pwd)"

# 启动 Gunicorn
echo "🎯 启动 Gunicorn 服务..."
# 使用最终版本（基于原有代码，添加文件持久化）
exec gunicorn --config gunicorn.conf.py "render_app_final:app"
