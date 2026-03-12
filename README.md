# 维宝宁销售话术对练AI Agent

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://semver.org)
[![Python](https://img.shields.io/badge/python-3.9+-green.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

> 首个国产长效曲普瑞林微球（维宝宁®）销售话术AI对练系统

---

## 🎯 项目简介

本项目是一个基于AI的医药销售话术训练系统，专为**维宝宁®（注射用醋酸曲普瑞林微球）**设计。系统提供：

- 🤖 AI医生角色扮演（5种医生类型）
- 💬 实时销售话术对练
- 📊 智能评估反馈（5维度评估）
- 📈 学习进度追踪
- 📚 完整产品知识库

**适用对象**：医药代表、销售培训师

---

## ✨ 核心功能

### 1. 医生角色扮演
| 角色 | 类型 | 难度 | 特点 |
|------|------|------|------|
| 主任级专家 | 学术型 | ⭐⭐⭐⭐⭐ | 注重循证医学，谨慎决策 |
| 科室主任 | 管理型 | ⭐⭐⭐⭐ | 注重效果，关心成本 |
| 主治医师 | 实用型 | ⭐⭐⭐ | 注重经验，开放尝试 |
| 住院医师 | 学习型 | ⭐⭐ | 学习意愿强，决策权小 |
| 带组专家 | 影响力型 | ⭐⭐⭐⭐⭐ | 学术临床并重，影响力大 |

### 2. 对练场景
- 完整拜访流程
- 价格异议处理
- 竞品对比应对
- 安全性质疑
- 学术型专家拜访
- 时间紧张快速拜访
- 异议处理专项训练

### 3. 智能评估
| 维度 | 权重 | 内容 |
|------|------|------|
| 产品知识 | 25% | 适应症、用法用量、核心卖点 |
| 话术规范 | 20% | FAB法则、SPIN技巧 |
| 异议处理 | 25% | APRC法则、证据支持 |
| 沟通礼仪 | 15% | 称呼、语气、时间把握 |
| 专业形象 | 15% | 术语准确、自信度 |

---

## 📦 项目结构

```
weibaoning-sales-training/
├── 📄 文档
│   ├── README.md                      # 本文件
│   ├── SKILL.md                       # OpenClaw技能文档
│   ├── PROJECT_REPORT.md              # 项目完成报告
│   ├── DEPLOY_COMPLETE_GUIDE.md       # 完整部署指南 ⭐
│   ├── DEPLOY_CHECKLIST.md            # 部署检查清单
│   ├── USER_MANUAL.md                 # 用户使用手册
│   └── .env.example                   # 环境变量模板
│
├── 📚 知识库 (references/)
│   ├── product-knowledge.md           # 产品知识 (988行)
│   ├── sales-scripts.md               # 销售话术 (503行)
│   ├── lecture-notes.md               # 科室会演讲备注 (256行)
│   ├── objections-handling.md         # 异议处理 (741行)
│   ├── doctor-profiles.md             # 医生角色 (243行)
│   └── scenarios.md                   # 对练场景 (273行)
│
├── 🔧 脚本 (scripts/)
│   ├── start_practice.py              # 开始对练
│   ├── evaluate_response.py           # 评估回答
│   ├── generate_report.py             # 生成报告
│   ├── feishu_bot.py                  # 飞书机器人
│   ├── wechat_bot.py                  # 微信机器人
│   └── deploy.sh                      # 一键部署脚本
│
├── 🐳 部署配置
│   ├── Dockerfile                     # Docker镜像
│   ├── docker-compose.yml             # Docker Compose
│   ├── nginx.conf                     # Nginx配置
│   └── requirements.txt               # Python依赖
│
└── 📂 数据目录 (data/)
    ├── sessions/                      # 会话数据
    ├── reports/                       # 学习报告
    └── users/                         # 用户数据
```

---

## 🚀 快速开始

### 方式一：Docker部署（推荐）

```bash
# 1. 克隆代码
git clone https://github.com/your-repo/weibaoning-sales-training.git
cd weibaoning-sales-training

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入飞书/微信配置

# 3. 启动服务
docker-compose up -d

# 4. 查看状态
docker-compose ps
```

### 方式二：手动部署

```bash
# 1. 运行一键部署脚本
curl -fsSL https://raw.githubusercontent.com/your-repo/deploy.sh | sudo bash

# 2. 配置环境变量
sudo nano /opt/weibaoning-sales-training/.env

# 3. 重启服务
sudo supervisorctl restart all
```

详细部署指南：[DEPLOY_COMPLETE_GUIDE.md](DEPLOY_COMPLETE_GUIDE.md)

---

## 📖 使用说明

### 基本指令

| 指令 | 功能 |
|------|------|
| `开始练习` | 开始新的对练 |
| `结束` | 结束当前对练 |
| `查看报告` | 查看学习报告 |
| `查询 [关键词]` | 查询产品知识 |
| `帮助` | 显示帮助菜单 |

### 使用流程

```
1. 发送"开始练习"
2. 选择医生角色（1-5）
3. 根据AI医生提问回复销售话术
4. 接收评估反馈
5. 发送"结束"查看学习报告
```

详细使用说明：[USER_MANUAL.md](USER_MANUAL.md)

---

## 📊 知识库统计

| 类别 | 内容量 | 来源 |
|------|--------|------|
| 产品知识 | 988行 | 说明书、DA资料、III期临床 |
| 销售话术 | 503行 | 科室会讲稿、实战话术 |
| 演讲备注 | 256行 | 完整25页科室会演讲备注 |
| 异议处理 | 741行 | 9类常见异议应对 |
| 医生角色 | 243行 | 5种医生类型详细设定 |
| 对练场景 | 273行 | 7种实战场景 |
| **总计** | **3,004行** | **6份资料整合** |

---

## 🏥 适应症覆盖

### 前列腺癌
- 局部晚期前列腺癌
- 转移性前列腺癌
- ADT治疗金标准
- 联合用药方案

### 子宫内膜异位症
- 疼痛管理
- 复发预防
- 生育力保护
- 术前/术后治疗

---

## 🔧 技术栈

- **后端**：Python 3.9 + Flask
- **部署**：Docker + Docker Compose + Nginx
- **消息**：飞书机器人API + 微信公众号API
- **数据**：SQLite
- **监控**：Supervisor + Loguru

---

## 📈 性能指标

- **响应时间**：< 500ms
- **并发支持**：100+ 用户同时在线
- **可用性**：99.9%
- **部署时间**：15-30分钟

---

## 🛣️ 路线图

### v1.0.0（当前）
- ✅ 飞书机器人
- ✅ 基础对练功能
- ✅ 5维度评估
- ✅ 知识库查询

### v1.1.0（计划）
- 📅 微信公众号接入
- 📅 语音输入支持
- 📅 学习报告导出

### v1.2.0（计划）
- 📅 微信小程序
- 📅 AI语音对练
- 📅 个性化推荐

### v2.0.0（计划）
- 📅 CRM系统集成
- 📅 多产品支持
- 📅 大数据分析

---

## 🤝 贡献指南

欢迎提交Issue和PR！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

---

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

---

## 🙏 致谢

- 丽珠医药集团股份有限公司
- 维宝宁®产品团队
- 所有参与测试的医药代表

---

**让每一次销售拜访都更加专业！** 💪

---

*项目链接：[GitHub Repository](https://github.com/your-repo/weibaoning-sales-training)*  
*文档链接：[完整文档](DEPLOY_COMPLETE_GUIDE.md)*  
*问题反馈：[Issues](https://github.com/your-repo/weibaoning-sales-training/issues)*
