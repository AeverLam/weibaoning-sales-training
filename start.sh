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
# 使用AI智能版（支持智能追问、自然过渡、新评分维度）
exec gunicorn --config gunicorn.conf.py "render_app_ai:app"