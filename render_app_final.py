#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
维宝宁销售培训机器人 - AI智能版 (文件持久化版本)
基于原有代码，仅添加会话持久化功能
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
# 智谱 AI (GLM-4) 配置
ZHIPU_API_KEY = os.environ.get("ZHIPU_API_KEY", "")
ZHIPU_API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

# 飞书配置
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "cli_a938ac2a24391bcb")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")

# 数据存储目录
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
SESSIONS_DIR = os.path.join(DATA_DIR, 'sessions')
PROCESSED_MSG_FILE = os.path.join(DATA_DIR, 'processed_messages.json')
os.makedirs(SESSIONS_DIR, exist_ok=True)

# 内存缓存（启动时从文件加载）
sessions = {}  # session_id -> session_data
user_progress = {}  # user_id -> progress_data
user_sessions = {}  # feishu_user_id -> session_id 或 "selecting_doctor"
processed_messages = set()  # 已处理的消息ID，用于去重
_sent_messages_cache = {}  # 发送消息去重缓存 {user_id: {content_hash: timestamp}}

# ============ 消息去重持久化 ============
def load_processed_messages():
    """加载已处理的消息ID"""
    global processed_messages
    if os.path.exists(PROCESSED_MSG_FILE):
        try:
            with open(PROCESSED_MSG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 只保留最近24小时的消息ID
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
        
        # 清理24小时前的记录
        cutoff_time = time.time() - 86400
        data = {k: v for k, v in data.items() if v > cutoff_time}
        
        # 添加新记录
        data[message_id] = time.time()
        
        with open(PROCESSED_MSG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving processed message: {e}")

# 启动时加载已处理的消息
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

# 启动时加载会话
load_all_sessions()

# ============ 医生角色定义（妇科/生殖科） ============
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

# ============ 对话场景定义 ============
DIALOGUE_SCENARIOS = [
    {
        "round": 1,
        "topic": "开场与需求探询",
        "doctor_init": "你好，请问有什么事吗？",
        "goal": "建立信任，了解医生对子宫内膜容受性问题的管理痛点",
        "evaluation_points": ["礼貌开场", "探询需求", "倾听反馈"]
    },
    {
        "round": 2,
        "topic": "产品引入",
        "doctor_init": "我们科室确实有不少反复种植失败的患者，你们有什么产品？",
        "goal": "自然引入维宝宁，引起医生兴趣",
        "evaluation_points": ["产品介绍清晰", "突出核心优势", "关联医生需求"]
    },
    {
        "round": 3,
        "topic": "机制阐述",
        "doctor_init": "维宝宁？没用过，它是什么机制？",
        "goal": "清晰阐述维宝宁改善子宫内膜容受性的作用机制",
        "evaluation_points": ["机制解释准确", "通俗易懂", "突出创新性"]
    },
    {
        "round": 4,
        "topic": "临床证据",
        "doctor_init": "有临床研究数据支持吗？",
        "goal": "介绍关键研究数据和临床案例",
        "evaluation_points": ["数据准确", "突出关键结果", "与标准治疗对比"]
    },
    {
        "round": 5,
        "topic": "安全性讨论",
        "doctor_init": "这个药安全性怎么样？有什么副作用？",
        "goal": "客观说明安全性，处理不良反应顾虑",
        "evaluation_points": ["客观说明", "对比竞品安全性", "处理顾虑"]
    },
    {
        "round": 6,
        "topic": "用法用量",
        "doctor_init": "怎么用？起始剂量多少？",
        "goal": "说明起始剂量、使用方法、注意事项",
        "evaluation_points": ["剂量准确", "使用方案清晰", "禁忌症说明"]
    },
    {
        "round": 7,
        "topic": "处理异议",
        "doctor_init": "价格好像不便宜啊？",
        "goal": "处理价格异议，突出价值",
        "evaluation_points": ["理解顾虑", "价值转化", "提供支持"]
    },
    {
        "round": 8,
        "topic": "缔结与跟进",
        "doctor_init": "行，我考虑考虑。",
        "goal": "促成试用，确定跟进计划",
        "evaluation_points": ["促成行动", "明确下一步", "建立长期关系"]
    }
]

# ============ AI 对话生成函数 ============
def generate_doctor_reply(user_message, session_data, round_num):
    """使用智谱 AI (GLM-4) 生成医生回复"""
    
    if not ZHIPU_API_KEY:
        print("ERROR: ZHIPU_API_KEY is empty!")
        return get_fallback_reply(round_num, session_data.get("doctor_type", "副主任医师"))
    
    doctor = DOCTOR_PROFILES[session_data["doctor_type"]]
    scenario = DIALOGUE_SCENARIOS[round_num - 1]
    
    # 构建系统提示
    system_prompt = f"""你是{doctor['title']} {doctor['name']}，正在接待医药代表拜访。

你的性格特点：{doctor['personality']}
你关注的重点：{', '.join(doctor['concerns'])}
当前难度等级：{doctor['difficulty']}/5

当前对话场景（第{round_num}轮）：{scenario['topic']}
场景描述：{scenario['doctor_init']}
本轮目标：{scenario['goal']}

【重要】你必须根据医药代表的回答内容来回复：
- 如果回答专业、有针对性，表现出兴趣和认可
- 如果回答敷衍、不专业，表现出质疑或追问
- 回复要自然真实，符合医生身份，不要机械重复

要求：
1. 以医生的身份和口吻回复，自然真实
2. 根据难度等级调整问题深度（难度越高，问题越专业/刁钻）
3. 可以提出质疑、表达顾虑、或表示认可
4. 回复简短（2-4句话），符合真实对话场景
5. 【关键】必须针对医药代表的回答内容做出回应，不能自说自话"""
    
    # 构建对话历史
    messages = [{"role": "system", "content": system_prompt}]
    
    # 添加历史对话
    for msg in session_data.get("history", []):
        if msg["role"] == "user":
            messages.append({"role": "user", "content": msg["content"]})
        else:
            messages.append({"role": "assistant", "content": msg["content"]})
    
    # 添加当前用户消息
    messages.append({"role": "user", "content": user_message})
    
    # 调用智谱 AI (GLM-4) API
    headers = {
        "Authorization": f"Bearer {ZHIPU_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "glm-4",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 200
    }
    
    try:
        response = requests.post(ZHIPU_API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        if "choices" in result and len(result["choices"]) > 0:
            reply = result["choices"][0]["message"]["content"]
            return reply
        else:
            return get_fallback_reply(round_num, session_data["doctor_type"])
            
    except Exception as e:
        print(f"Zhipu API error: {e}")
        return get_fallback_reply(round_num, session_data["doctor_type"])

def evaluate_user_response(user_message, round_num):
    """评估用户回答质量"""
    
    scenario = DIALOGUE_SCENARIOS[round_num - 1]
    evaluation_points = scenario["evaluation_points"]
    
    # 构建评估提示
    eval_prompt = f"""你是一位严格的销售培训导师，请严格评估以下医药代表的拜访话术质量。

对话轮次：第{round_num}轮
场景：{scenario['topic']}
场景目标：{scenario['goal']}
评估维度：{', '.join(evaluation_points)}

医药代表说的话："{user_message}"

【评分标准】（请严格打分）：
- 18-20分：优秀 - 回答专业、完整、切中要害，超出预期
- 14-17分：良好 - 回答基本合格，但有改进空间
- 10-13分：及格 - 回答有缺陷，需要改进
- 6-9分：较差 - 回答不专业或偏离主题
- 1-5分：很差 - 回答完全错误、敷衍或不相关

【重要】如果回答敷衍、不专业、偏离主题或完全错误，必须给低分（10分以下）！

请从以下维度评分（每项1-5分）：
1. 内容准确性 - 信息是否正确、专业
2. 表达清晰度 - 逻辑是否清晰、易懂
3. 客户需求匹配度 - 是否回应了医生的关切
4. 专业度 - 是否体现医药代表的专业素养

【关键】只返回纯文本评价，不要返回JSON格式。格式如下：
评分：X/20
评价：（具体评价和建议，指出具体问题）
优点：（优点1；优点2）
改进：（改进建议1；改进建议2）"""
    
    headers = {
        "Authorization": f"Bearer {ZHIPU_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "glm-4",
        "messages": [{"role": "user", "content": eval_prompt}],
        "temperature": 0.3,
        "max_tokens": 500
    }
    
    try:
        response = requests.post(ZHIPU_API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        if "choices" in result and len(result["choices"]) > 0:
            content = result["choices"][0]["message"]["content"]
            # 解析评分
            score = 10  # 默认
            feedback = content
            strengths = ["积极参与"]
            improvements = ["继续提升专业度"]
            
            # 尝试提取评分
            try:
                for line in content.split('\n'):
                    if '评分：' in line or '评分:' in line:
                        score_str = line.split('：')[-1].split(':')[-1].strip()
                        score = int(score_str.split('/')[0])
                        break
            except:
                pass
            
            return {
                "score": score,
                "feedback": feedback[:200],
                "strengths": strengths,
                "improvements": improvements
            }
    except Exception as e:
        print(f"Evaluation error: {e}")
    
    # 默认评估
    return {
        "score": 10,
        "feedback": "回答需要改进，建议更专业地阐述产品知识。",
        "strengths": ["积极参与"],
        "improvements": ["需要更具体地阐述产品优势", "建议提前准备话术"]
    }

def get_fallback_reply(round_num, doctor_type):
    """备用回复（API失败时使用）"""
    
    fallbacks = {
        1: "嗯，你说说看。",
        2: "这个我了解一下，你们产品有什么特点？",
        3: "作用机制是什么？",
        4: "有什么临床数据吗？",
        5: "安全性怎么样？",
        6: "怎么用？",
        7: "价格怎么样？",
        8: "好的，我考虑一下。"
    }
    
    return fallbacks.get(round_num, "请继续说。")

def generate_summary(session_data):
    """生成8轮对话总结报告"""
    
    evaluations = session_data.get("evaluations", [])
    total_score = sum(r.get("score", 0) for r in evaluations)
    avg_score = total_score / 8 if len(evaluations) > 0 else 0
    
    doctor = DOCTOR_PROFILES[session_data["doctor_type"]]
    
    # 计算等级
    if avg_score >= 16:
        level = "优秀"
        level_emoji = "🏆"
    elif avg_score >= 12:
        level = "良好"
        level_emoji = "👍"
    elif avg_score >= 8:
        level = "及格"
        level_emoji = "📖"
    else:
        level = "需改进"
        level_emoji = "💪"
    
    summary = f"""{level_emoji} 拜访演练总结报告

📊 总体表现
• 医生角色：{doctor['title']} {doctor['name']}
• 难度等级：{"⭐" * doctor['difficulty']}
• 总得分：{total_score}/160
• 平均分：{avg_score:.1f}/20
• 综合评级：{level}

📝 各轮表现
"""
    
    for i, eval_data in enumerate(evaluations, 1):
        scenario = DIALOGUE_SCENARIOS[i-1]
        score = eval_data.get('score', 0)
        stars = "⭐" * min(score // 4, 5)
        
        summary += f"""
第{i}轮：{scenario['topic']}
得分：{score}/20 {stars}
评价：{eval_data.get('feedback', '无')[:100]}...
"""
    
    # 提取优点和改进建议
    all_strengths = []
    all_improvements = []
    for e in evaluations:
        all_strengths.extend(e.get('strengths', []))
        all_improvements.extend(e.get('improvements', []))
    
    unique_strengths = list(dict.fromkeys(all_strengths))[:3]
    unique_improvements = list(dict.fromkeys(all_improvements))[:3]
    
    summary += f"""
💡 总体建议

继续保持：
"""
    for s in unique_strengths:
        summary += f"• {s}\n"
    
    summary += f"""
重点提升：
"""
    for i in unique_improvements:
        summary += f"• {i}\n"
    
    summary += f"""
下次目标：争取总分达到 {min(total_score + 30, 160)} 分以上

生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""
    
    return summary

_recent_sent_messages = {}  # 最近发送的消息缓存 {user_id: [(content_hash, timestamp), ...]}

def send_feishu_message(open_id, user_id, reply_text):
    """发送飞书消息（独立函数，用于后台线程）"""
    global _recent_sent_messages
    
    try:
        # 检查是否重复发送（60秒内相同内容不重复发送）
        content_hash = hash(reply_text[:200])
        current_time = time.time()
        
        if user_id not in _recent_sent_messages:
            _recent_sent_messages[user_id] = []
        
        # 清理60秒前的记录
        _recent_sent_messages[user_id] = [
            (h, t) for h, t in _recent_sent_messages[user_id]
            if current_time - t < 60
        ]
        
        # 检查是否重复
        for h, t in _recent_sent_messages[user_id]:
            if h == content_hash and (current_time - t) < 60:
                print(f"Duplicate send detected for user {user_id}, skipping")
                return
        
        # 记录本次发送
        _recent_sent_messages[user_id].append((content_hash, current_time))
        # 获取 tenant_access_token
        token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        token_resp = requests.post(
            token_url,
            json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET},
            timeout=10
        )
        token_data = token_resp.json()
        
        token = token_data.get("tenant_access_token")
        if not token:
            print(f"Failed to get token!")
            return
        
        # 发送消息
        send_url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        receive_id = open_id if open_id else user_id
        
        # 如果消息太长，分段发送
        max_length = 3000
        if len(reply_text) > max_length:
            parts = [reply_text[i:i+max_length] for i in range(0, len(reply_text), max_length)]
            for part in parts:
                payload = {
                    "receive_id": receive_id,
                    "content": json.dumps({"text": part}, ensure_ascii=False),
                    "msg_type": "text"
                }
                send_resp = requests.post(send_url, headers=headers, json=payload, timeout=10)
                print(f"Send response: {send_resp.json()}")
        else:
            payload = {
                "receive_id": receive_id,
                "content": json.dumps({"text": reply_text}, ensure_ascii=False),
                "msg_type": "text"
            }
            send_resp = requests.post(send_url, headers=headers, json=payload, timeout=10)
            print(f"Send response: {send_resp.json()}")
            
    except Exception as e:
        print(f"Send message error: {str(e)}")
        import traceback
        print(traceback.format_exc())

def process_message_async(open_id, user_id, text, message_id):
    """异步处理消息"""
    # 检查消息是否已处理（内存+文件双重检查）
    if message_id in processed_messages:
        print(f"Message {message_id} already processed (memory), skip")
        return
    
    # 保存到文件（持久化去重）
    save_processed_message(message_id)
    processed_messages.add(message_id)
    
    # 生成回复
    reply_text = generate_reply(open_id, user_id, text)
    
    # 检查是否重复发送（内容去重）
    content_hash = hash(f"{user_id}:{reply_text[:100]}")
    current_time = time.time()
    
    if user_id in _sent_messages_cache:
        last_sent = _sent_messages_cache[user_id].get(content_hash)
        if last_sent and (current_time - last_sent) < 30:  # 30秒内不重复发送相同内容
            print(f"Duplicate content detected for user {user_id}, skip sending")
            return
    else:
        _sent_messages_cache[user_id] = {}
    
    _sent_messages_cache[user_id][content_hash] = current_time
    
    # 发送消息
    send_feishu_message(open_id, user_id, reply_text)

def generate_reply(open_id, user_id, text):
    """生成回复内容"""
    
    # 开始指令
    if text in ["/start", "开始", "开始训练", "开始练习"]:
        reply_text = """🎯 请选择医生角色开始训练：

1️⃣ 主任医师 - 难度⭐⭐⭐⭐⭐
   权威严谨，问题深入，适合高手挑战

2️⃣ 副主任医师 - 难度⭐⭐⭐⭐
   务实关注性价比，标准难度（推荐）

3️⃣ 主治医师 - 难度⭐⭐⭐
   学习意愿强，问题基础，适合新手

请回复数字 1、2 或 3 选择医生"""
        user_sessions[user_id] = "selecting_doctor"
        return reply_text
    
    # 医生选择
    elif text in ["1", "2", "3"] and user_sessions.get(user_id) == "selecting_doctor":
        doctor_map = {"1": "主任医师", "2": "副主任医师", "3": "主治医师"}
        doctor_type = doctor_map.get(text, "副主任医师")
        
        session_id = str(uuid.uuid4())
        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "doctor_type": doctor_type,
            "current_round": 1,
            "history": [],
            "evaluations": [],
            "start_time": datetime.now().isoformat(),
            "status": "active"
        }
        sessions[session_id] = session_data
        save_session_to_file(session_id, session_data)  # 保存到文件
        user_sessions[user_id] = session_id
        
        scenario = DIALOGUE_SCENARIOS[0]
        doctor = DOCTOR_PROFILES[doctor_type]
        
        return f"""🎯 销售话术对练开始！

👨‍⚕️ 医生角色：{doctor['title']} {doctor['name']}
难度：{'⭐' * doctor['difficulty']}

{doctor['name']}：{scenario['doctor_init']}

💡 第1轮/共8轮：{scenario['topic']}
🎯 目标：{scenario['goal']}"""
    
    # 帮助
    elif text in ["/help", "帮助", "?", "？"]:
        return """🎯 维宝宁销售培训机器人

【可用指令】
• 开始 / start - 开始新的训练
• 1/2/3 - 选择医生难度
• / 帮助 - 显示帮助信息

【训练说明】
• 共8轮对话，模拟真实拜访场景
• AI医生会根据你的回答智能回复
• 每轮都有评分和反馈（满分20分）
• 完成后生成总结报告

发送「开始」即可开始训练！"""
    
    # 检查是否正在选择医生
    elif user_sessions.get(user_id) == "selecting_doctor":
        return "请选择医生：回复 1（主任医师）、2（副主任医师）或 3（主治医师）"
    
    # 检查是否有活跃会话
    elif user_id in user_sessions and user_sessions[user_id] not in [None, "selecting_doctor"]:
        session_id = user_sessions[user_id]
        
        # 优先从内存加载，如果没有则从文件加载
        if session_id not in sessions:
            session_data = load_session_from_file(session_id)
            if session_data:
                sessions[session_id] = session_data
            else:
                return "会话已过期，请发送「开始」重新开始"
        
        session = sessions[session_id]
        current_round = session["current_round"]
        
        if current_round > 8:
            summary = generate_summary(session)
            delete_session_file(session_id)  # 删除文件
            del user_sessions[user_id]
            return summary + "\n\n🎉 训练结束！发送「开始」可重新练习。"
        
        # AI对话
        session["history"].append({
            "role": "user",
            "content": text,
            "round": current_round
        })
        
        doctor_reply = generate_doctor_reply(text, session, current_round)
        evaluation = evaluate_user_response(text, current_round)
        session["evaluations"].append(evaluation)
        session["history"].append({
            "role": "doctor",
            "content": doctor_reply,
            "round": current_round
        })
        
        if current_round == 8:
            session["status"] = "completed"
            save_session_to_file(session_id, session)  # 保存到文件
            summary = generate_summary(session)
            delete_session_file(session_id)  # 删除文件
            del user_sessions[user_id]
            return f"""👨‍⚕️ {doctor_reply}

{summary}

🎉 训练结束！发送「开始」可重新练习。"""
        else:
            session["current_round"] = current_round + 1
            save_session_to_file(session_id, session)  # 保存到文件
            next_round = session["current_round"]
            next_scenario = DIALOGUE_SCENARIOS[next_round - 1]
            score = evaluation.get('score', 10)
            feedback = evaluation.get('feedback', '继续加油')[:80]
            
            return f"""👨‍⚕️ {doctor_reply}

💡 第{next_round}轮/共8轮：{next_scenario['topic']}
🎯 目标：{next_scenario['goal']}

📊 上轮评分：{score}/20
💬 反馈：{feedback}..."""
    
    else:
        return "请先发送「开始」或「/start」开始训练"

# ============ 飞书适配接口 ============

@app.route("/webhook/feishu", methods=["POST", "GET"])
@app.route("/api/feishu/chat", methods=["POST", "GET"])  # 兼容旧版地址
def feishu_chat():
    """处理飞书消息 - 立即返回，异步处理"""
    # 获取原始数据
    raw_data = request.get_data(as_text=True)
    data = json.loads(raw_data) if raw_data else {}
    
    # 飞书验证 - 返回 challenge
    if "challenge" in data:
        return jsonify({"challenge": data["challenge"]})
    
    # 解析消息
    event = data.get("event", {})
    message = event.get("message", {})
    sender = event.get("sender", {})
    sender_id = sender.get("sender_id", {})
    user_id = sender_id.get("user_id", "")
    open_id = sender_id.get("open_id", "")
    message_id = message.get("message_id", "")
    
    # 获取消息内容
    content_str = message.get("content", "{}")
    try:
        content = json.loads(content_str) if isinstance(content_str, str) else content_str
    except:
        content = {}
    text = content.get("text", "").strip()
    
    print(f"=== Received Feishu message ===")
    print(f"Message ID: {message_id}")
    print(f"User: {user_id}")
    print(f"Text: {text}")
    
    # 检查消息是否已处理（内存+文件双重检查）
    if message_id in processed_messages:
        print(f"Message {message_id} already processed (memory), return 200 immediately")
        return jsonify({"code": 0, "msg": "success"})
    
    # 检查文件中的记录（防止服务重启后重复处理）
    if os.path.exists(PROCESSED_MSG_FILE):
        try:
            with open(PROCESSED_MSG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if message_id in data:
                    print(f"Message {message_id} already processed (file), return 200 immediately")
                    processed_messages.add(message_id)  # 添加到内存缓存
                    return jsonify({"code": 0, "msg": "success"})
        except:
            pass
    
    # 立即返回200，防止飞书重试
    # 启动后台线程处理消息（带异常保护）
    def safe_process():
        try:
            process_message_async(open_id, user_id, text, message_id)
        except Exception as e:
            print(f"Error in process_message_async: {e}")
            import traceback
            print(traceback.format_exc())
    
    thread = threading.Thread(target=safe_process)
    thread.daemon = True
    thread.start()
    
    return jsonify({"code": 0, "msg": "success"})

# ============ API 路由 ============

@app.route("/")
def index():
    return jsonify({"status": "ok", "version": "ai-persistent-v2.3", "features": ["AI智能对话", "智谱GLM-4", "实时评估", "会话持久化", "8轮场景"]})

@app.route("/health")
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

@app.route("/api/start", methods=["POST"])
def start_session():
    """开始新的培训会话"""
    data = request.json or {}
    user_id = data.get("user_id", "anonymous")
    doctor_type = data.get("doctor_type", "副主任医师")
    
    if doctor_type not in DOCTOR_PROFILES:
        doctor_type = "副主任医师"
    
    session_id = str(uuid.uuid4())
    session_data = {
        "session_id": session_id,
        "user_id": user_id,
        "doctor_type": doctor_type,
        "current_round": 1,
        "history": [],
        "evaluations": [],
        "start_time": datetime.now().isoformat(),
        "status": "active"
    }
    sessions[session_id] = session_data
    save_session_to_file(session_id, session_data)  # 保存到文件
    
    scenario = DIALOGUE_SCENARIOS[0]
    doctor = DOCTOR_PROFILES[doctor_type]
    
    welcome_msg = f"""👨‍⚕️ **{doctor['title']} {doctor['name']}**

*{scenario['doctor_init']}*

---

💡 **第1轮/共8轮**：{scenario['topic']}
🎯 **目标**：{scenario['goal']}"""
    
    return jsonify({
        "session_id": session_id,
        "message": welcome_msg,
        "round": 1,
        "doctor_type": doctor_type
    })

@app.route("/api/chat", methods=["POST"])
def chat():
    """处理对话"""
    data = request.json or {}
    session_id = data.get("session_id")
    user_message = data.get("message", "")
    
    if not session_id:
        return jsonify({"error": "会话不存在或已过期，请重新开始"}), 400
    
    # 优先从内存加载，如果没有则从文件加载
    if session_id not in sessions:
        session_data = load_session_from_file(session_id)
        if session_data:
            sessions[session_id] = session_data
        else:
            return jsonify({"error": "会话不存在或已过期，请重新开始"}), 400
    
    session = sessions[session_id]
    current_round = session["current_round"]
    
    if current_round > 8:
        return jsonify({"error": "对话已完成"}), 400
    
    # 记录用户消息
    session["history"].append({
        "role": "user",
        "content": user_message,
        "round": current_round
    })
    
    # 生成医生回复
    doctor_reply = generate_doctor_reply(user_message, session, current_round)
    
    # 评估用户回答
    evaluation = evaluate_user_response(user_message, current_round)
    session["evaluations"].append(evaluation)
    
    # 记录医生回复
    session["history"].append({
        "role": "doctor",
        "content": doctor_reply,
        "round": current_round
    })
    
    # 保存到文件
    save_session_to_file(session_id, session)
    
    return jsonify({
        "doctor_reply": doctor_reply,
        "evaluation": evaluation,
        "round": current_round
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
