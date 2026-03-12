# Gunicorn 配置文件
# 用于 Render 部署

import os
import multiprocessing

# 服务器套接字绑定
bind = "0.0.0.0:" + os.environ.get("PORT", "5000")

# 工作进程数 - Render免费版使用1个worker
workers = 1

# 工作进程类型 - 使用gevent支持异步
worker_class = "sync"

# 超时时间（秒）
timeout = 120

# 保持连接时间（秒）
keepalive = 5

# 日志级别
loglevel = "info"

# 访问日志
accesslog = "-"

# 错误日志
errorlog = "-"

# 进程名称
proc_name = "weibaoning-bot"

# 预加载应用
preload_app = True
