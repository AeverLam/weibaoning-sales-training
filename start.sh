#!/bin/bash
echo "🚀 启动维宝宁销售话术对练..."
PORT=${PORT:-5000}
echo "📋 端口: $PORT"
exec gunicorn --config gunicorn.conf.py render_app:app
