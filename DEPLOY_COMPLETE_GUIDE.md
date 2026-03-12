# 维宝宁销售话术对练AI Agent - 自部署完整方案

**版本**：v1.0.0  
**部署方式**：Docker（推荐）/ 手动部署  
**预计部署时间**：15-30分钟  

---

## 🚀 方案一：Docker部署（推荐）

### 前提条件
- 一台Linux服务器（Ubuntu 20.04+ / CentOS 8+）
- 已安装 Docker 和 Docker Compose
- 服务器有公网IP
- 已注册飞书/微信开发者账号

### 步骤1：获取代码
```bash
git clone https://github.com/your-repo/weibaoning-sales-training.git
cd weibaoning-sales-training
```

### 步骤2：配置环境变量
```bash
# 复制环境变量模板
cp .env.example .env

# 编辑配置文件
nano .env

# 填入以下内容：
FEISHU_APP_ID=cli_xxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
FEISHU_ENCRYPT_KEY=xxxxxxxxxxxxxxxx
FEISHU_VERIFICATION_TOKEN=xxxxxxxx

WECHAT_TOKEN=your_wechat_token
WECHAT_APP_ID=wx_xxxxxxxxxxxxxxxx
WECHAT_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 步骤3：启动服务
```bash
# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f

# 查看状态
docker-compose ps
```

### 步骤4：配置飞书/微信
1. 登录飞书开放平台：https://open.feishu.cn/
2. 进入您的应用
3. 事件订阅 → 请求URL配置：
   - 飞书：`http://您的服务器IP/webhook/feishu`
4. 保存并发布应用

---

## 🛠️ 方案二：手动部署

### 步骤1：服务器准备
```bash
# 购买云服务器（推荐阿里云/腾讯云）
# 配置：2核4G，Ubuntu 20.04，带宽5Mbps

# 连接到服务器
ssh root@您的服务器IP
```

### 步骤2：运行一键部署脚本
```bash
# 下载部署脚本
curl -fsSL https://raw.githubusercontent.com/your-repo/deploy.sh -o deploy.sh

# 运行部署脚本
chmod +x deploy.sh
sudo ./deploy.sh

# 按提示完成配置
```

### 步骤3：配置环境变量
```bash
# 编辑环境变量
sudo nano /opt/weibaoning-sales-training/.env

# 填入飞书/微信配置
# 保存并退出
```

### 步骤4：重启服务
```bash
sudo supervisorctl restart all
sudo systemctl restart nginx
```

---

## 📋 配置飞书机器人（详细步骤）

### 1. 创建应用
```
1. 访问 https://open.feishu.cn/
2. 点击"创建企业自建应用"
3. 填写应用信息：
   - 应用名称：维宝宁销售训练助手
   - 应用描述：医药代表销售话术AI对练
   - 应用头像：上传维宝宁logo
```

### 2. 获取凭证
```
1. 进入应用 → 凭证与基础信息
2. 复制：
   - App ID: cli_xxxxxxxxxxxx
   - App Secret: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
3. 保存到 .env 文件
```

### 3. 配置权限
```
1. 进入"权限管理"
2. 添加以下权限：
   ✅ 读取用户手机号
   ✅ 获取用户user ID
   ✅ 给多个用户批量发消息
   ✅ 获取用户邮箱信息
   ✅ 获取用户User ID
```

### 4. 配置事件订阅
```
1. 进入"事件订阅"
2. 配置请求URL：
   http://您的服务器IP/webhook/feishu
   
3. 点击"验证"
4. 如果验证成功，保存配置
```

### 5. 发布应用
```
1. 进入"版本管理与发布"
2. 点击"创建版本"
3. 设置可用范围：全员
4. 提交发布
```

---

## 📋 配置微信公众号（详细步骤）

### 1. 注册公众号
```
1. 访问 https://mp.weixin.qq.com/
2. 注册服务号（需企业认证）
3. 完成微信认证
```

### 2. 配置服务器
```
1. 进入"开发" → "基本配置"
2. 服务器配置：
   - URL: http://您的服务器IP/webhook/wechat
   - Token: 自定义Token（保存到.env）
   - EncodingAESKey: 随机生成
3. 点击"提交"验证
```

### 3. 获取AppID和AppSecret
```
1. 在"基本配置"页面
2. 复制：
   - AppID: wx_xxxxxxxxxxxxxxxx
   - AppSecret: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
3. 保存到 .env 文件
```

---

## 🔒 安全加固

### 配置HTTPS（推荐）
```bash
# 安装Certbot
sudo apt install certbot python3-certbot-nginx

# 申请SSL证书
sudo certbot --nginx -d your-domain.com

# 自动续期
sudo certbot renew --dry-run
```

### 配置防火墙
```bash
# 仅开放必要端口
sudo ufw default deny incoming
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

### 配置访问日志
```bash
# 查看访问日志
docker-compose logs -f nginx

# 查看应用日志
docker-compose logs -f feishu-bot
docker-compose logs -f wechat-bot
```

---

## 🧪 测试验证

### 测试飞书机器人
```
1. 在飞书搜索"维宝宁销售训练助手"
2. 添加机器人为好友
3. 发送：开始练习
4. 选择医生角色：2
5. 根据提示进行对练
```

### 测试微信机器人
```
1. 关注微信公众号
2. 发送：开始练习
3. 按提示操作
```

### 检查服务状态
```bash
# Docker方式
docker-compose ps
docker-compose logs

# 手动方式
sudo supervisorctl status
sudo systemctl status nginx
```

---

## 🔄 日常维护

### 查看日志
```bash
# Docker
docker-compose logs -f --tail=100

# 手动
tail -f /opt/weibaoning-sales-training/logs/*.log
```

### 备份数据
```bash
# 备份数据目录
tar -czvf backup-$(date +%Y%m%d).tar.gz ./data

# 定期备份（可配置cron）
0 2 * * * /path/to/backup.sh
```

### 更新部署
```bash
# 拉取最新代码
git pull

# 重新构建
docker-compose down
docker-compose up -d --build

# 或手动更新
cd /opt/weibaoning-sales-training
git pull
sudo supervisorctl restart all
```

---

## 🆘 常见问题

### Q1：飞书验证URL失败
**解决方案**：
1. 检查服务器防火墙是否开放80端口
2. 确认 .env 配置正确
3. 查看日志：`docker-compose logs feishu-bot`

### Q2：微信Token验证失败
**解决方案**：
1. 确认Token与微信公众平台配置一致
2. 检查服务器时间是否准确
3. 确认URL可访问

### Q3：服务启动失败
**解决方案**：
```bash
# 检查端口占用
sudo netstat -tlnp | grep 5000

# 重启服务
docker-compose restart

# 查看详细日志
docker-compose logs --tail=200
```

### Q4：知识库内容需要更新
**解决方案**：
```bash
# 编辑知识库文件
nano references/product-knowledge.md

# 重启服务生效
docker-compose restart
```

---

## 📞 技术支持

**部署遇到问题？**

1. 查看日志定位问题
2. 检查配置文件
3. 参考常见问题章节
4. 联系技术支持

---

**恭喜！部署完成后，您的团队就可以开始使用AI销售训练助手了！** 🎉

---

*部署文档版本：v1.0.0*  
*最后更新：2026-03-11*
