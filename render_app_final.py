#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
维宝宁销售培训机器人 - 完整修复版
包含：5医生角色、智能追问、自然过渡、新评分维度
"""

import os
import json
import time
import uuid
import requests
import threading
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

# ============ 配置 ============
ZHIPU_API_KEY = os.environ.get("ZHIPU_API_KEY", "")
ZHIPU_API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "cli_a938ac2a24391bcb")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")

# 数据存储目录
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
SESSIONS_DIR = os.path.join(DATA_DIR, 'sessions')
PROCESSED_MSG_FILE = os.path.join(DATA_DIR, 'processed_messages.json')
os.makedirs(SESSIONS_DIR, exist_ok=True)

# 内存缓存
sessions = {}
user_progress = {}
user_sessions = {}
processed_messages = set()
_sent_messages_cache = {}

# ============ 消息去重持久化 ============
def load_processed_messages():
    """加载已处理的消息ID"""
    global processed_messages
    if os.path.exists(PROCESSED_MSG_FILE):
        try:
            with open(PROCESSED_MSG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                cutoff_time = time.time() - 86400
                processed_messages = set(
                    msg_id for msg_id, timestamp in data.items()
                    if timestamp > cutoff_time
                )
                print(f"Loaded {len(processed_messages)} processed messages")
        except Exception as e:
            print(f"Error loading processed messages: {e}")
            processed_messages = set()

def save_processed_message(message_id):
    """保存已处理的消息ID"""
    try:
        data = {}
        if os.path.exists(PROCESSED_MSG_FILE):
            with open(PROCESSED_MSG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        cutoff_time = time.time() - 86400
        data = {k: v for k, v in data.items() if v > cutoff_time}
        data[message_id] = time.time()
        with open(PROCESSED_MSG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving processed message: {e}")

load_processed_messages()

# ============ 持久化函数 ============
def save_session_to_file(session_id, session_data):
    """保存会话到文件"""
    filepath = os.path.join(SESSIONS_DIR, f"{session_id}.json")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(session_data, f, ensure_ascii=False, indent=2)

def load_session_from_file(session_id):
    """从文件加载会话"""
    filepath = os.path.join(SESSIONS_DIR, f"{session_id}.json")
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def delete_session_file(session_id):
    """删除会话文件"""
    filepath = os.path.join(SESSIONS_DIR, f"{session_id}.json")
    if os.path.exists(filepath):
        os.remove(filepath)

def load_all_sessions():
    """启动时加载所有会话"""
    global sessions
    if os.path.exists(SESSIONS_DIR):
        for filename in os.listdir(SESSIONS_DIR):
            if filename.endswith('.json'):
                session_id = filename[:-5]
                session_data = load_session_from_file(session_id)
                if session_data:
                    sessions[session_id] = session_data

load_all_sessions()

# ============ 5个医生角色定义 ============
DOCTOR_PROFILES = {
    "1": {
        "name": "张主任",
        "title": "主任级专家",
        "type": "学术型",
        "personality": "权威、严谨、注重临床证据，对新产品持谨慎态度，喜欢问深层次问题",
        "concerns": ["疗效数据", "安全性", "指南推荐", "医保政策", "患者依从性"],
        "difficulty": 5,
        "stars": "⭐⭐⭐⭐⭐"
    },
    "2": {
        "name": "李医生",
        "title": "科室主任",
        "type": "管理型",
        "personality": "务实、关注性价比、喜欢对比竞品，时间紧张，注重效率",
        "concerns": ["价格", "患者依从性", "与竞品的差异", "临床使用便利性", "联合用药"],
        "difficulty": 4,
        "stars": "⭐⭐⭐⭐"
    },
    "3": {
        "name": "王医生",
        "title": "主治医师",
        "type": "实用型",
        "personality": "学习意愿强、关注新知识、会问基础问题，对改善子宫内膜容受性产品感兴趣",
        "concerns": ["适应症", "用法用量", "不良反应", "患者教育", "临床案例"],
        "difficulty": 3,
        "stars": "⭐⭐⭐"
    },
    "4": {
        "name": "陈医生",
        "title": "住院医师",
        "type": "学习型",
        "personality": "谦虚好学、听从上级、基础扎实但经验不足，需要详细指导",
        "concerns": ["基础知识", "适应症", "禁忌症", "上级意见", "学习资料"],
        "difficulty": 2,
        "stars": "⭐⭐"
    },
    "5": {
        "name": "刘主任",
        "title": "带组专家",
        "type": "影响力型",
        "personality": "学术影响力大、决策权高、关注学科发展，对创新产品持开放态度",
        "concerns": ["学术价值", "学科发展", "教学价值", "学术合作", "影响力提升"],
        "difficulty": 5,
        "stars": "⭐⭐⭐⭐⭐"
    }
}

# ============ 8轮对话场景定义 ============
DIALOGUE_SCENARIOS = [
    {
        "round": 1,
        "topic": "开场与需求探询",
        "doctor_init": "你好，请问有什么事吗？",
        "goal": "建立信任，了解医生对子宫内膜容受性问题的管理痛点"
    },
    {
        "round": 2,
        "topic": "产品引入",
        "goal": "自然引入维宝宁，引起医生兴趣"
    },
    {
        "round": 3,
        "topic": "作用机制",
        "goal": "清晰阐述维宝宁改善子宫内膜容受性的作用机制"
    },
    {
        "round": 4,
        "topic": "临床证据",
        "goal": "介绍关键研究数据和临床案例"
    },
    {
        "round": 5,
        "topic": "安全性讨论",
        "goal": "客观说明安全性，处理不良反应顾虑"
    },
    {
        "round": 6,
        "topic": "用法用量",
        "goal": "说明起始剂量、使用方法、注意事项"
    },
    {
        "round": 7,
        "topic": "处理异议",
        "goal": "处理价格异议，突出价值"
    },
    {
        "round": 8,
        "topic": "缔结与跟进",
        "goal": "促成试用，确定跟进计划"
    }
]

# ============ 评分维度（新） ============
# 每轮10分：内容准确性3分 + 表达清晰度2分 + 客户需求匹配2分 + 专业度2分 + 加分项1分

# ============ 飞书API函数 ============
def get_feishu_token():
    """获取飞书tenant_access_token"""
    try:
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        resp = requests.post(url, json={
            "app_id": FEISHU_APP_ID,
            "app_secret": FEISHU_APP_SECRET
        }, timeout=10)
        return resp.json().get("tenant_access_token")
    except Exception as e:
        print(f"Error getting token: {e}")
        return None

def send_feishu_message(user_id, msg_id, text):
    """发送消息到飞书"""
    def do_send():
        try:
            token = get_feishu_token()
            if not token:
                return
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            if msg_id:
                url = f"https://open.feishu.cn/open-apis/im/v1/messages/{msg_id}/reply"
                data = {
                    "msg_type": "text",
                    "content": json.dumps({"text": text})
                }
            else:
                url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"
                data = {
                    "receive_id": user_id,
                    "msg_type": "text",
                    "content": json.dumps({"text": text})
                }
            requests.post(url, headers=headers, json=data, timeout=10)
        except Exception as e:
            print(f"Error sending message: {e}")
    threading.Thread(target=do_send, daemon=True).start()

# ============ 智谱AI API调用 ============
def call_zhipu_ai(messages, temperature=0.7):
    """调用智谱AI API"""
    try:
        headers = {
            "Authorization": f"Bearer {ZHIPU_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "glm-4",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 500
        }
        resp = requests.post(ZHIPU_API_URL, headers=headers, json=data, timeout=30)
        result = resp.json()
        if 'choices' in result and len(result['choices']) > 0:
            return result['choices'][0]['message']['content']
        return None
    except Exception as e:
        print(f"Error calling Zhipu AI: {e}")
        return None

# ============ 核心逻辑函数 ============
def should_advance_round(doctor_reply, exchange_count):
    """判断是否应该推进到下一轮"""
    # 最多3轮强制推进
    if exchange_count >= 3:
        return True
    
    # 如果有明确的推进标记，直接推进
    if "【推进到下一轮】" in doctor_reply:
        return True
    
    # 语义判断：医生是否已开启新话题
    clean_reply = doctor_reply.replace("【推进到下一轮】", "").strip()
    
    # 检查是否包含话题转换信号词
    transition_signals = [
        "说到", "谈到", "关于", "至于", "接下来", "那", "那么",
        "我们聊聊", "说说", "讲讲", "看看", "聊聊", "说说看"
    ]
    has_transition = any(signal in clean_reply for signal in transition_signals)
    
    # 检查是否以问句结束
    ends_with_new_question = clean_reply.endswith(("?", "？"))
    
    # 推进条件：有过渡信号 + 以新问题结束 + 至少已对话1轮
    if has_transition and ends_with_new_question and exchange_count >= 1:
        return True
    
    return False

def evaluate_response(user_message, doctor_context, round_num, follow_up_count):
    """评估用户回答质量（新评分维度）"""
    eval_prompt = f"""你是一位销售培训专家，正在评估医药代表的回答质量。

**当前轮次**：第{round_num}轮
**医生问题/陈述**：{doctor_context}
**医药代表回答**：{user_message}
**追问次数**：{follow_up_count}次

**评估维度**（总分10分）：
1. 内容准确性（0-3分）：信息是否正确、专业，数据是否准确
2. 表达清晰度（0-2分）：逻辑是否清晰、易懂，结构是否合理
3. 客户需求匹配（0-2分）：是否回应了医生的关切和问题
4. 专业度（0-2分）：是否体现专业素养，术语使用是否得当
5. 加分项（0-1分）：是否有超出预期的亮点

**追问惩罚**：
- 0次追问：不扣分
- 1次追问：扣0.5分
- 2次追问：扣1分
- 3次追问：扣2分

**评分标准**：
- 9-10分：优秀
- 7-8分：良好
- 5-6分：合格
- 0-4分：待提升

**是否需要追问**：
如果回答得分低于6分或过于简短（少于30字），应该追问。

请输出JSON格式：
{{
  "content_accuracy": 分数,
  "expression_clarity": 分数,
  "customer_match": 分数,
  "professionalism": 分数,
  "bonus": 分数,
  "total_score": 总分,
  "grade": "等级(A/B/C/D/F)",
  "need_follow_up": true/false,
  "follow_up_question": "如果需要追问，写出追问内容",
  "strengths": ["亮点1", "亮点2"],
  "weaknesses": ["改进点1", "改进点2"],
  "feedback": "个性化反馈建议"
}}"""
    
    messages = [
        {"role": "system", "content": "你是一位专业的医药销售培训专家。"},
        {"role": "user", "content": eval_prompt}
    ]
    
    result = call_zhipu_ai(messages, temperature=0.3)
    if result:
        try:
            # 提取JSON
            import re
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                eval_data = json.loads(json_match.group())
                # 应用追问惩罚
                base_score = eval_data.get('total_score', 5)
                penalty = {0: 0, 1: 0.5, 2: 1, 3: 2}.get(follow_up_count, 2)
                final_score = max(0, base_score - penalty)
                eval_data['total_score'] = round(final_score, 1)
                return eval_data
        except:
            pass
    
    # 默认评分
    return {
        "content_accuracy": 2,
        "expression_clarity": 1.5,
        "customer_match": 1.5,
        "professionalism": 1.5,
        "bonus": 0,
        "total_score": 6.5 - {0: 0, 1: 0.5, 2: 1, 3: 2}.get(follow_up_count, 2),
        "grade": "C",
        "need_follow_up": len(user_message) < 30,
        "follow_up_question": "能详细说说吗？我想了解更多细节。",
        "strengths": ["态度积极"],
        "weaknesses": ["可以更加详细"],
        "feedback": "回答需要更加具体和专业。"
    }

def generate_doctor_reply(session_data, user_message):
    """生成医生回复"""
    doctor_type = session_data.get('doctor_type', '3')
    doctor_profile = DOCTOR_PROFILES.get(doctor_type, DOCTOR_PROFILES['3'])
    current_round = session_data.get('current_round', 1)
    exchange_count = session_data.get('exchange_count', 0)
    
    scenario = DIALOGUE_SCENARIOS[current_round - 1] if current_round <= len(DIALOGUE_SCENARIOS) else DIALOGUE_SCENARIOS[-1]
    
    # 构建对话历史
    history = session_data.get('messages', [])
    history_text = "\n".join([f"{'医生' if msg['role'] == 'doctor' else '代表'}：{msg['content']}" for msg in history[-6:]])
    
    prompt = f"""你是一位{doctor_profile['title']}（{doctor_profile['type']}），{doctor_profile['personality']}。

**当前场景**：{scenario['topic']}
**本轮目标**：{scenario['goal']}
**当前是第{current_round}轮，本轮已对话{exchange_count}次**

**对话历史**：
{history_text}

**医药代表最新回答**：{user_message}

**回复规则**：
1. 保持医生角色，用第一人称"我"
2. 根据回答质量决定是追问还是推进：
   - 如果回答不充分（简短、模糊、未回应关切）：追问当前话题，不要推进
   - 如果回答充分且满意：一句话完成三件事：
     a) 简要认可/总结上轮（陈述句）
     b) 用过渡词引出下轮话题（如"说到"、"关于"、"那"）
     c) 用问句提出下轮的第一个问题
     d) 加上【推进到下一轮】标记

3. 追问示例：
   "除了疼痛，患者还有其他不适吗？"
   
4. 推进示例：
   "明白了，内异症确实棘手。说到产品，维宝宁在这方面有什么特点？【推进到下一轮】"

5. 每次回复控制在2-3句话，保持对话节奏

请生成医生回复："""
    
    messages = [
        {"role": "system", "content": "你是一位专业的妇科/生殖科医生，正在进行医药代表拜访。"},
        {"role": "user", "content": prompt}
    ]
    
    reply = call_zhipu_ai(messages)
    return reply if reply else "嗯，继续说，我在听。"

# ============ 主处理函数 ============
def handle_user_message(user_id, message_text, msg_id):
    """处理用户消息"""
    message_text = message_text.strip()
    
    # 开始练习
    if message_text in ['开始练习', 'start', '开始', '开始对练']:
        # 清除旧会话
        if user_id in user_sessions:
            old_session_id = user_sessions[user_id]
            delete_session_file(old_session_id)
            if old_session_id in sessions:
                del sessions[old_session_id]
            del user_sessions[user_id]
        
        return """👋 欢迎开始维宝宁销售话术对练！

请选择医生角色（回复数字 1-5）：

1️⃣ 主任级专家 ⭐⭐⭐⭐⭐ - 学术型、严谨、注重证据
2️⃣ 科室主任 ⭐⭐⭐⭐ - 管理型、务实、时间紧  
3️⃣ 主治医师 ⭐⭐⭐ - 实用型、经验导向
4️⃣ 住院医师 ⭐⭐ - 学习型、听从上级
5️⃣ 带组专家 ⭐⭐⭐⭐⭐ - 影响力型、决策权高

💡 提示：不同医生类型有不同的关注点和提问风格"""
    
    # 结束练习
    if message_text in ['结束', 'stop', '退出']:
        if user_id in user_sessions:
            old_session_id = user_sessions[user_id]
            delete_session_file(old_session_id)
            if old_session_id in sessions:
                del sessions[old_session_id]
            del user_sessions[user_id]
        return "对练已结束。发送【开始练习】重新开始"
    
    # 帮助
    if message_text in ['帮助', 'help', '?']:
        return """📖 使用帮助

【开始练习】- 开始新的对练
【结束】- 结束当前对练
【帮助】- 查看帮助

**对练流程**：
1. 选择医生角色（1-5）
2. AI医生会根据你的回答智能回复
3. 如果回答不充分，AI会追问（最多3次）
4. 每轮结束后给出评分和反馈
5. 完成8轮后生成最终报告

**评分维度（每轮10分）**：
- 内容准确性（0-3分）
- 表达清晰度（0-2分）
- 客户需求匹配（0-2分）
- 专业度（0-2分）
- 加分项（0-1分）
- 追问惩罚（-0.5/-1/-2分）"""
    
    # 选择医生角色
    if message_text in ['1', '2', '3', '4', '5'] and (user_id not in user_sessions or user_sessions.get(user_id) == "selecting"):
        doctor_profile = DOCTOR_PROFILES[message_text]
        session_id = str(uuid.uuid4())
        
        session_data = {
            'session_id': session_id,
            'user_id': user_id,
            'doctor_type': message_text,
            'doctor_name': doctor_profile['name'],
            'current_round': 1,
            'exchange_count': 0,
            'follow_up_count': 0,
            'messages': [],
            'scores': [],
            'created_at': datetime.now().isoformat()
        }
        
        sessions[session_id] = session_data
        user_sessions[user_id] = session_id
        save_session_to_file(session_id, session_data)
        
        # 获取医生开场白
        scenario = DIALOGUE_SCENARIOS[0]
        
        return f"""✅ 已选择：{doctor_profile['title']} {doctor_profile['stars']}
类型：{doctor_profile['type']}
难度：{doctor_profile['stars']}

🎬 对练开始！

👨‍⚕️ **医生说：**
{scenario['doctor_init']}

💡 第1轮/共8轮：{scenario['topic']}
🎯 目标：{scenario['goal']}

💬 **请回复你的开场白...**"""
    
    # 如果没有活跃会话
    if user_id not in user_sessions or user_sessions[user_id] not in sessions:
        return "发送【开始练习】开始新的对练，或发送【帮助】查看使用说明"
    
    # 处理对话
    session_id = user_sessions[user_id]
    session_data = sessions[session_id]
    
    # 记录用户消息
    session_data['messages'].append({
        'role': 'user',
        'content': message_text,
        'timestamp': datetime.now().isoformat()
    })
    
    # 生成医生回复
    doctor_reply = generate_doctor_reply(session_data, message_text)
    
    # 判断是否推进
    should_advance = should_advance_round(doctor_reply, session_data.get('exchange_count', 0))
    
    if should_advance:
        # 本轮结束，进行评估
        follow_up_count = session_data.get('follow_up_count', 0)
        
        # 找到医生的问题（去掉推进标记）
        doctor_question = doctor_reply.replace("【推进到下一轮】", "").strip()
        
        # 评估
        evaluation = evaluate_response(message_text, doctor_question, session_data['current_round'], follow_up_count)
        
        # 记录评分
        session_data['scores'].append({
            'round': session_data['current_round'],
            'score': evaluation['total_score'],
            'evaluation': evaluation
        })
        
        # 更新会话
        session_data['current_round'] += 1
        session_data['exchange_count'] = 0
        session_data['follow_up_count'] = 0
        
        # 记录医生回复
        session_data['messages'].append({
            'role': 'doctor',
            'content': doctor_reply,
            'timestamp': datetime.now().isoformat()
        })
        
        save_session_to_file(session_id, session_data)
        
        # 检查是否完成8轮
        if session_data['current_round'] > 8:
            # 生成最终报告
            total_score = sum(s['score'] for s in session_data['scores']) / len(session_data['scores'])
            
            report = f"""🎉 对练完成！

📊 **综合评分：{total_score:.1f}/10**

**各轮得分：**
"""
            for s in session_data['scores']:
                report += f"第{s['round']}轮：{s['score']}/10\n"
            
            # 清理会话
            delete_session_file(session_id)
            del sessions[session_id]
            del user_sessions[user_id]
            
            return report
        
        # 继续下一轮
        next_scenario = DIALOGUE_SCENARIOS[session_data['current_round'] - 1]
        clean_reply = doctor_reply.replace("【推进到下一轮】", "").strip()
        
        reply = f"""👨‍⚕️ **医生说：**
{clean_reply}

---
📊 **第{session_data['current_round'] - 1}轮评分：{evaluation['total_score']}/10（等级{evaluation['grade']}）**
💬 **反馈：** {evaluation['feedback']}

💡 第{session_data['current_round']}轮/共8轮：{next_scenario['topic']}
🎯 目标：{next_scenario['goal']}

💬 **请继续回复...**"""
        
        return reply
    
    else:
        # 继续本轮，追问
        session_data['exchange_count'] += 1
        session_data['follow_up_count'] += 1
        
        # 记录医生回复
        session_data['messages'].append({
            'role': 'doctor',
            'content': doctor_reply,
            'timestamp': datetime.now().isoformat()
        })
        
        save_session_to_file(session_id, session_data)
        
        current_scenario = DIALOGUE_SCENARIOS[session_data['current_round'] - 1]
        
        reply = f"""👨‍⚕️ **医生说：**
{doctor_reply}

---
💡 第{session_data['current_round']}轮/共8轮：{current_scenario['topic']}
🎯 目标：{current_scenario['goal']}

💬 **请补充回答...**"""
        
        return reply

# ============ Flask路由 ============
@app.route('/')
def index():
    return jsonify({'status': 'ok', 'version': 'v3.0', 'features': ['5医生角色', '智能追问', '自然过渡', '新评分维度']})

@app.route('/webhook/feishu', methods=['POST', 'GET'])
def webhook():
    try:
        if request.method == 'GET':
            return jsonify({'status': 'ok'})
        
        data = request.get_json() or {}
        
        # 处理挑战验证
        if 'challenge' in data:
            return jsonify({'challenge': data['challenge']})
        
        header = data.get('header', {})
        event = data.get('event', {})
        event_type = header.get('event_type', '')
        
        if event_type in ['im.message.receive_v1', 'im.message.p2p_msg']:
            message = event.get('message', {})
            sender = event.get('sender', {})
            
            if message.get('message_type') == 'text':
                try:
                    content = json.loads(message.get('content', '{}'))
                    text = content.get('text', '').strip()
                except:
                    text = str(message.get('content', '')).strip()
                
                # 清理@机器人的内容
                text = text.replace('@_user_1', '').replace('@维宝宁销售训练助手', '').strip()
                
                user_id = sender.get('sender_id', {}).get('open_id', '')
                msg_id = message.get('message_id', '')
                
                # 消息去重
                if msg_id in processed_messages:
                    return jsonify({'status': 'ok'})
                processed_messages.add(msg_id)
                save_processed_message(msg_id)
                
                if text and user_id:
                    reply = handle_user_message(user_id, text, msg_id)
                    send_feishu_message(user_id, msg_id, reply)
        
        return jsonify({'status': 'ok'})
    except Exception as e:
        import traceback
        print(f"Error: {e}")
        print(traceback.format_exc())
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)