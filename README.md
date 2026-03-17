# 维宝宁销售话术对练 - 智能飞书机器人 v2.0

## 升级内容

### 1. 智能对练系统
- ✅ 基于LLM的智能医生角色扮演
- ✅ 5种医生角色（主任级专家、科室主任、主治医师、住院医师、带组专家）
- ✅ 8轮完整销售流程（开场白→探询需求→产品介绍→处理异议→促成成交→结束）
- ✅ 每轮自动评分（1-10分）

### 2. 对话状态管理
- ✅ 内存存储用户对话状态
- ✅ 30分钟无活动自动过期
- ✅ 支持多用户同时对话
- ✅ 修复了消息重置bug

### 3. 产品知识库
- ✅ 自动加载 references/ 目录下的所有资料
  - product-knowledge.md (产品知识)
  - sales-scripts.md (销售话术)
  - doctor-profiles.md (医生角色)
  - objections-handling.md (异议处理)
  - scenarios.md (对练场景)
  - lecture-notes.md (科室会演讲)

### 4. LLM集成
- ✅ 支持 OpenAI API / Claude API
- ✅ 智能生成医生回复
- ✅ 自动评估销售表现
- ✅ 无API Key时自动使用Mock回复

## 环境变量配置

```bash
# 飞书配置
export FEISHU_APP_ID="cli_a938ac2a24391bcb"
export FEISHU_APP_SECRET="your_app_secret"

# LLM配置 (可选，不配置则使用Mock模式)
export LLM_API_KEY="your_openai_api_key"
export LLM_API_URL="https://api.openai.com/v1/chat/completions"
export LLM_MODEL="gpt-4"

# 服务端口
export PORT=5000
```

## 使用方法

### 启动服务
```bash
python render_app.py
```

### 飞书交互命令

| 命令 | 说明 |
|------|------|
| `开始练习` / `start` | 开始新的对练 |
| `帮助` / `help` | 显示帮助菜单 |
| `状态` / `status` | 查看当前对练状态 |
| `结束` / `stop` | 结束对练并查看成绩 |

### 对练流程

1. 发送 `开始练习`
2. 选择医生角色（1-5）
3. 根据场景与AI医生进行8轮对话
4. 查看评估报告和改进建议

## 项目结构

```
weibaoning-sales-training/
├── render_app.py          # 主程序（智能对练机器人）
├── references/            # 产品资料目录
│   ├── product-knowledge.md
│   ├── sales-scripts.md
│   ├── doctor-profiles.md
│   ├── objections-handling.md
│   ├── scenarios.md
│   └── lecture-notes.md
└── README.md             # 本文件
```

## 核心功能说明

### ConversationManager（对话状态管理）
- 管理每个用户的对话状态
- 自动处理对话过期
- 记录对话历史和评分

### KnowledgeBase（知识库）
- 加载所有产品资料
- 提供医生角色配置
- 管理对话阶段定义

### LLMClient（LLM客户端）
- 调用LLM生成医生回复
- 自动提取评分
- 支持Mock模式（无API Key时）

### FeishuMessageHandler（消息处理器）
- 处理用户命令
- 管理对练流程
- 生成评估报告

## 版本历史

- v2.0.0 (2026-03-17): 重大升级，实现智能对练系统
- v1.0.1: 基础关键词匹配版本
