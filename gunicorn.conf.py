import os

bind = "0.0.0.0:" + os.environ.get("PORT", "5000")
workers = 1
worker_class = "sync"
timeout = 120
keepalive = 5
loglevel = "info"
accesslog = "-"
errorlog = "-"
proc_name = "weibaoning-bot"
preload_app = True
