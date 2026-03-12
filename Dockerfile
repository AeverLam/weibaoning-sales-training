# 维宝宁销售话术对练AI Agent - Docker部署

FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建数据目录
RUN mkdir -p /app/data/sessions /app/data/reports /app/data/users

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV APP_ENV=production
ENV DATA_DIR=/app/data

# 暴露端口
EXPOSE 5000 5001

# 启动命令
CMD ["python3", "-m", "scripts.feishu_bot_server"]
