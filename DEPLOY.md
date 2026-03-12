# 维宝宁销售话术对练 - Render 部署指南

## 🚀 快速部署步骤

### 1. 准备代码
确保以下文件在项目中：
- `render_app.py` - Flask Web 服务
- `requirements-render.txt` - Python 依赖
- `start.sh` - 启动脚本
- `gunicorn.conf.py` - Gunicorn 配置
- `render.yaml` - Render 部署配置
- `scripts/` 目录 - 业务逻辑脚本

### 2. 推送到 GitHub
```bash
# 如果还没有 GitHub 仓库
git init
git add .
git commit -m "Initial commit for Render deployment"
git remote add origin https://github.com/yourusername/weibaoning-bot.git
git push -u origin main
```

### 3. 在 Render 上部署

#### 方式A：通过 Blueprint（推荐）
1. 登录 [Render Dashboard](https://dashboard.render.com)
2. 点击 "New +" → "Blueprint"
3. 连接 GitHub 仓库
4. Render 会自动读取 `render.yaml` 配置
5. 设置 `FEISHU_APP_SECRET` 环境变量
6. 点击部署

#### 方式B：手动创建
1. 登录 [Render Dashboard](https://dashboard.render.com)
2. 点击 "New +" → "Web Service"
3. 连接 GitHub 仓库
4. 配置：
   - **Name**: `weibaoning-feishu-bot`
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements-render.txt`
   - **Start Command**: `bash start.sh`
5. 添加环境变量：
   - `FEISHU_APP_ID`: `cli_a938ac2a24391bcb`
   - `FEISHU_APP_SECRET`: 您的App Secret
6. 点击 "Create Web Service"

### 4. 获取 Webhook URL
部署完成后，Render 会分配一个 URL：
```
https://weibaoning-feishu-bot.onrender.com
```

Webhook 地址为：
```
https://weibaoning-feishu-bot.onrender.com/webhook/feishu
```

### 5. 配置飞书应用

1. 登录 [飞书开放平台](https://open.feishu.cn/)
2. 进入您的应用
3. 点击 "事件订阅"
4. 设置请求URL：
   ```
   https://weibaoning-feishu-bot.onrender.com/webhook/feishu
   ```
5. 添加订阅事件：
   - 接收消息 `im.message.receive_v1`
6. 点击保存并验证

### 6. 添加机器人能力
1. 进入 "机器人" 页面
2. 启用机器人
3. 配置机器人信息（名称、头像、介绍）
4. 保存

### 7. 发布应用
1. 进入 "版本管理与发布"
2. 点击 "创建版本"
3. 填写版本信息
4. 发布到企业

## 🔧 环境变量

| 变量名 | 说明 | 必需 |
|--------|------|------|
| `FEISHU_APP_ID` | 飞书 App ID | ✅ |
| `FEISHU_APP_SECRET` | 飞书 App Secret | ✅ |
| `FEISHU_ENCRYPT_KEY` | 消息加密密钥 | ❌ |
| `FEISHU_VERIFICATION_TOKEN` | 验证令牌 | ❌ |
| `PORT` | 服务端口（Render自动设置） | ✅ |

## 🧪 测试服务

### 测试健康检查
```bash
curl https://weibaoning-feishu-bot.onrender.com/health
```

### 测试消息处理
```bash
curl -X POST https://weibaoning-feishu-bot.onrender.com/webhook/feishu/test \
  -H "Content-Type: application/json" \
  -d '{"text": "开始练习", "user_id": "test001"}'
```

## 📁 项目结构

```
weibaoning-sales-training/
├── render_app.py              # Flask Web 服务入口
├── requirements-render.txt    # Render 依赖
├── start.sh                   # 启动脚本
├── gunicorn.conf.py          # Gunicorn 配置
├── render.yaml               # Render 部署配置
├── DEPLOY.md                 # 本文件
├── scripts/
│   ├── feishu_bot.py         # 飞书消息处理逻辑
│   ├── start_practice.py     # 开始对练
│   ├── evaluate_response.py  # 评估回答
│   └── generate_report.py    # 生成报告
├── data/                     # 数据目录
└── knowledge/                # 知识库
```

## ⚠️ 注意事项

1. **Render 免费版限制**:
   - 服务会在15分钟无请求后休眠
   - 首次唤醒可能需要10-30秒
   - 每月750小时免费额度

2. **飞书配置**:
   - 确保 Webhook URL 配置正确
   - 保存配置时会验证URL，服务必须先部署

3. **日志查看**:
   - 在 Render Dashboard 查看实时日志
   - 日志保留7天

## 🐛 故障排查

### 服务无法启动
```bash
# 检查日志
render logs weibaoning-feishu-bot

# 本地测试
python render_app.py
```

### 飞书验证失败
1. 确认服务已部署并可访问
2. 检查环境变量设置
3. 确认URL格式正确

### 消息无响应
1. 检查事件订阅是否开启
2. 确认订阅了 `im.message.receive_v1` 事件
3. 查看 Render 日志

## 📞 支持

- Render 文档: https://render.com/docs
- 飞书开放平台: https://open.feishu.cn/
