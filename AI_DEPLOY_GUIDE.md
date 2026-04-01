# 维宝宁销售话术对练 - AI智能版部署指南

## 🎉 方案B已实现：AI智能对话

### 新功能

✅ **AI智能医生回复**
- 使用LLM根据用户回答生成个性化医生回复
- 不再是固定脚本，每次对话都不同
- 医生角色性格保持一致，但回复灵活多变

✅ **实时评估系统**
- 每轮对话后立即评估用户回答
- 5个维度评分：产品知识、话术规范、异议处理、沟通礼仪、专业形象
- 使用LLM进行智能评估，比规则评分更准确

✅ **个性化反馈**
- 每轮给出具体亮点和改进建议
- 最终报告包含：综合评分、各维度得分、亮点总结、改进建议、学习推荐
- 基于整个对话历史生成个性化评价

---

## 📁 新增文件

| 文件 | 说明 |
|------|------|
| `scripts/ai_dialogue_engine.py` | AI对话引擎核心代码 |
| `render_app_ai.py` | 集成AI功能的飞书机器人 |

---

## 🚀 部署步骤

### 1. 代码准备

确保以下文件已上传到服务器：
```
skills/weibaoning-sales-training/
├── scripts/
│   ├── ai_dialogue_engine.py    # 新增
│   ├── start_practice.py
│   └── ...
├── render_app_ai.py              # 新增（主程序）
└── ...
```

### 2. 环境变量配置

需要配置LLM API密钥（至少配置一个）：

```bash
# OpenAI
export OPENAI_API_KEY="sk-..."

# Claude
export ANTHROPIC_API_KEY="sk-ant-..."

# Kimi/Moonshot（推荐，国内可用）
export MOONSHOT_API_KEY="..."

# 或者通用配置
export LLM_API_KEY="your-api-key"
export LLM_MODEL="moonshot/kimi-k2.5"  # 或其他模型
```

### 3. 依赖安装

```bash
cd skills/weibaoning-sales-training

# 如果使用OpenAI
pip install openai

# 如果使用Claude
pip install anthropic

# 如果使用Kimi（通过OpenAI SDK）
pip install openai
```

### 4. 启动服务

```bash
# 开发模式
python render_app_ai.py

# 生产模式（使用gunicorn）
gunicorn -c gunicorn.conf.py render_app_ai:app
```

### 5. 飞书机器人配置

更新飞书机器人的Webhook URL指向新的服务地址：
```
https://your-domain.com/webhook/feishu
```

---

## 🔧 配置选项

### LLM模型选择

在 `ai_dialogue_engine.py` 中修改 `_call_llm` 方法：

```python
# 默认使用Kimi（国内推荐）
model = os.environ.get('LLM_MODEL', 'moonshot/kimi-k2.5')

# 可选模型：
# - openai/gpt-4
# - openai/gpt-3.5-turbo
# - anthropic/claude-3-sonnet
# - moonshot/kimi-k2.5
```

### 评分标准调整

在 `ai_dialogue_engine.py` 中修改评估Prompt：

```python
eval_prompt = f"""
... 
# 修改评分标准描述
- 9-10分：优秀...
- 7-8分：良好...
...
"""
```

### 对话轮数调整

默认8轮，在 `ai_dialogue_engine.py` 中修改：

```python
# process_turn 方法中
is_complete = self.round > 8  # 改为想要的轮数
```

---

## 📊 与旧版本对比

| 功能 | 旧版本（固定脚本） | 新版本（AI智能） |
|------|------------------|----------------|
| 医生回复 | 固定8句，不变化 | AI生成，灵活多变 |
| 评估方式 | 关键词匹配 | LLM智能评估 |
| 反馈内容 | 通用模板 | 个性化反馈 |
| 对话体验 | 机械、重复 | 真实、有挑战性 |
| 学习效果 | 有限 | 更接近真实场景 |

---

## 🧪 测试方法

### 本地测试

```bash
# 1. 启动服务
python render_app_ai.py

# 2. 使用curl测试
curl -X POST http://localhost:5000/api/practice/start \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","doctor_type":"科室主任"}'

# 3. 发送消息
curl -X POST http://localhost:5000/api/practice/message \
  -H "Content-Type: application/json" \
  -d '{"session_id":"xxx","message":"主任您好，我是丽珠医药的代表"}'
```

### 飞书测试

1. 给机器人发送【开始练习】
2. 选择医生角色（1-5）
3. 开始对话，观察AI医生的回复
4. 完成8轮后查看最终报告

---

## ⚠️ 注意事项

### API费用
- LLM API调用会产生费用
- 每轮对话调用2次API（生成回复+评估）
- 8轮对话 = 16次API调用
- 建议设置预算上限

### 备用方案
- 如果LLM API不可用，会自动切换到规则评分
- 医生回复会使用预设模板
- 确保基础功能始终可用

### 数据安全
- 对话内容会发送到LLM服务商
- 不要输入真实患者信息
- 遵守公司数据安全规定

---

## 🔮 未来优化方向

1. **多轮对话记忆优化** - 使用向量数据库存储对话历史
2. **语音对练** - 集成语音识别和合成
3. **视频模拟** - 生成医生形象进行视频对话
4. **知识库增强** - 接入维宝宁产品知识库
5. **学习路径推荐** - 基于薄弱项推荐学习资源

---

## 📞 技术支持

如有问题，请联系：
- 维护者：黄轩
- 创建日期：2026-04-01
- 版本：v2.0 AI智能版