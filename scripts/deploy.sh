#!/bin/bash
# 维宝宁销售话术对练AI Agent - 一键部署脚本
# 使用方法: ./deploy.sh [feishu|wechat|all]

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置
APP_NAME="weibaoning-sales-training"
APP_DIR="/opt/$APP_NAME"
SERVICE_USER="weibaoning"
PYTHON_VERSION="3.9"

# 检查root权限
check_root() {
    if [ "$EUID" -ne 0 ]; then 
        echo -e "${RED}请使用 sudo 运行此脚本${NC}"
        exit 1
    fi
}

# 安装系统依赖
install_system_deps() {
    echo -e "${YELLOW}正在安装系统依赖...${NC}"
    apt-get update
    apt-get install -y \
        python3-pip \
        python3-venv \
        nginx \
        supervisor \
        git \
        sqlite3 \
        curl \
        ufw
    echo -e "${GREEN}系统依赖安装完成${NC}"
}

# 创建用户
create_user() {
    echo -e "${YELLOW}创建服务用户...${NC}"
    if ! id "$SERVICE_USER" &>/dev/null; then
        useradd -r -s /bin/false -d "$APP_DIR" "$SERVICE_USER"
    fi
    echo -e "${GREEN}服务用户创建完成${NC}"
}

# 创建应用目录
setup_app_dir() {
    echo -e "${YELLOW}设置应用目录...${NC}"
    mkdir -p "$APP_DIR"
    mkdir -p "$APP_DIR/logs"
    mkdir -p "$APP_DIR/data"
    cp -r ../* "$APP_DIR/"
    chown -R "$SERVICE_USER:$SERVICE_USER" "$APP_DIR"
    echo -e "${GREEN}应用目录设置完成${NC}"
}

# 安装Python依赖
install_python_deps() {
    echo -e "${YELLOW}安装Python依赖...${NC}"
    cd "$APP_DIR"
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    deactivate
    echo -e "${GREEN}Python依赖安装完成${NC}"
}

# 配置环境变量
setup_env() {
    echo -e "${YELLOW}配置环境变量...${NC}"
    cat > "$APP_DIR/.env" << EOF
# 飞书配置
FEISHU_APP_ID=your_feishu_app_id
FEISHU_APP_SECRET=your_feishu_app_secret
FEISHU_ENCRYPT_KEY=your_encrypt_key
FEISHU_VERIFICATION_TOKEN=your_verification_token

# 微信配置
WECHAT_TOKEN=your_wechat_token
WECHAT_APP_ID=your_wechat_app_id
WECHAT_APP_SECRET=your_wechat_app_secret

# 应用配置
APP_ENV=production
APP_PORT=5000
WECHAT_PORT=5001
LOG_LEVEL=INFO
DATA_DIR=$APP_DIR/data
EOF
    chown "$SERVICE_USER:$SERVICE_USER" "$APP_DIR/.env"
    echo -e "${GREEN}环境变量配置完成${NC}"
    echo -e "${YELLOW}请编辑 $APP_DIR/.env 文件，填入实际的配置值${NC}"
}

# 创建supervisor配置
setup_supervisor() {
    echo -e "${YELLOW}配置Supervisor...${NC}"
    
    # 飞书机器人服务
    cat > /etc/supervisor/conf.d/${APP_NAME}-feishu.conf << EOF
[program:${APP_NAME}-feishu]
command=$APP_DIR/venv/bin/python $APP_DIR/scripts/feishu_bot_server.py
directory=$APP_DIR
user=$SERVICE_USER
autostart=true
autorestart=true
stderr_logfile=$APP_DIR/logs/feishu.err.log
stdout_logfile=$APP_DIR/logs/feishu.out.log
environment=PATH="$APP_DIR/venv/bin"
EOF

    # 微信机器人服务
    cat > /etc/supervisor/conf.d/${APP_NAME}-wechat.conf << EOF
[program:${APP_NAME}-wechat]
command=$APP_DIR/venv/bin/python $APP_DIR/scripts/wechat_bot.py
directory=$APP_DIR
user=$SERVICE_USER
autostart=true
autorestart=true
stderr_logfile=$APP_DIR/logs/wechat.err.log
stdout_logfile=$APP_DIR/logs/wechat.out.log
environment=PATH="$APP_DIR/venv/bin"
EOF

    supervisorctl reread
    supervisorctl update
    echo -e "${GREEN}Supervisor配置完成${NC}"
}

# 配置Nginx
setup_nginx() {
    echo -e "${YELLOW}配置Nginx...${NC}"
    
    cat > /etc/nginx/sites-available/$APP_NAME << EOF
server {
    listen 80;
    server_name _;  # 接受所有域名
    
    location /webhook/feishu {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
    
    location /webhook/wechat {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
    
    location / {
        return 200 '维宝宁销售话术对练服务运行中';
        add_header Content-Type text/plain;
    }
}
EOF

    ln -sf /etc/nginx/sites-available/$APP_NAME /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    nginx -t && systemctl restart nginx
    echo -e "${GREEN}Nginx配置完成${NC}"
}

# 配置防火墙
setup_firewall() {
    echo -e "${YELLOW}配置防火墙...${NC}"
    ufw default deny incoming
    ufw default allow outgoing
    ufw allow 22/tcp   # SSH
    ufw allow 80/tcp   # HTTP
    ufw allow 443/tcp  # HTTPS
    ufw --force enable
    echo -e "${GREEN}防火墙配置完成${NC}"
}

# 启动服务
start_services() {
    echo -e "${YELLOW}启动服务...${NC}"
    supervisorctl start ${APP_NAME}-feishu
    supervisorctl start ${APP_NAME}-wechat
    echo -e "${GREEN}服务启动完成${NC}"
}

# 显示状态
show_status() {
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  部署完成！${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "应用目录: $APP_DIR"
    echo "日志目录: $APP_DIR/logs"
    echo "数据目录: $APP_DIR/data"
    echo ""
    echo "服务状态:"
    supervisorctl status ${APP_NAME}-feishu
    supervisorctl status ${APP_NAME}-wechat
    echo ""
    echo -e "${YELLOW}下一步操作：${NC}"
    echo "1. 编辑配置文件: sudo nano $APP_DIR/.env"
    echo "2. 填入飞书/微信的AppID和AppSecret"
    echo "3. 重启服务: sudo supervisorctl restart all"
    echo ""
    echo -e "${YELLOW}飞书Webhook URL: http://您的服务器IP/webhook/feishu${NC}"
    echo -e "${YELLOW}微信Webhook URL: http://您的服务器IP/webhook/wechat${NC}"
    echo ""
}

# 主函数
main() {
    echo -e "${GREEN}开始部署 维宝宁销售话术对练AI Agent${NC}"
    echo "========================================"
    
    check_root
    install_system_deps
    create_user
    setup_app_dir
    install_python_deps
    setup_env
    setup_supervisor
    setup_nginx
    setup_firewall
    start_services
    show_status
}

# 运行主函数
main
