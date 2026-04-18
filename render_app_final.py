"""
维宝宁销售培训机器人 - 完整修复版
整合功能：智能追问 + 自然过渡 + 智能评分 + 推进标记
"""

import os
import json
import uuid
import threading
import requests
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

# ============ 配置 ============
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
ZHIPU_API_KEY = os.environ.get("ZHIPU_API_KEY", "")

# 存储
sessions = {}
user_sessions = {}
processed_messages = set()

# ============ 持久化消息去重 ============
PROCESSED_MESSAGES_FILE = "/tmp/processed_messages.json"
PROCESSED_MESSAGES_LOCK = threading.Lock()

def load_processed_messages():
    """从文件加载已处理的消息ID"""
    global processed_messages
    try:
        if os.path.exists(PROCESSED_MESSAGES_FILE):
            with open(PROCESSED_MESSAGES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 只保留7天内的记录
                cutoff_time = datetime.now().timestamp() - 7 * 24 * 3600
                processed_messages = {
                    msg_id for msg_id, timestamp in data.items()
                    if timestamp > cutoff_time
                }
                print(f"Loaded {len(processed_messages)} processed messages from file")
    except Exception as e:
        print(f"Error loading processed messages: {e}")
        processed_messages = set()

def save_processed_message(message_id):
    """保存已处理的消息ID到文件"""
    try:
        with PROCESSED_MESSAGES_LOCK:
            # 先读取现有数据
            data = {}
            if os.path.exists(PROCESSED_MESSAGES_FILE):
                with open(PROCESSED_MESSAGES_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            
            # 添加新记录
            data[message_id] = datetime.now().timestamp()
            
            # 清理7天前的记录
            cutoff_time = datetime.now().timestamp() - 7 * 24 * 3600
            data = {k: v for k, v in data.items() if v > cutoff_time}
            
            # 保存回文件
            with open(PROCESSED_MESSAGES_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving processed message: {e}")

# 启动时加载已处理的消息
load_processed_messages()

# ============ 医生角色配置 ============
DOCTOR_PROFILES = {
    "主任级专家": {
        "name": "陈教授",
        "title": "主任级专家",
        "difficulty": 5,
        "strictness": 0.95,
        "personality": "学术型、严谨、注重循证医学证据，对数据要求高，不轻易被说服",
        "opening_style": "严肃专业，直接问重点"
    },
    "科室主任": {
        "name": "刘主任",
        "title": "科室主任",
        "difficulty": 4,
        "strictness": 0.8,
        "personality": "管理型、务实、时间紧，关注科室效益和患者满意度",
        "opening_style": "礼貌但直接，关心实用性"
    },
    "主治医师": {
        "name": "张医生",
        "title": "主治医师",
        "difficulty": 3,
        "strictness": 0.6,
        "personality": "实用型、经验导向，关注临床实际效果",
        "opening_style": "友好开放，愿意交流"
    },
    "住院医师": {
        "name": "王医生",
        "title": "住院医师",
        "difficulty": 2,
        "strictness": 0.4,
        "personality": "学习型、听从上级，对新产品好奇但缺乏经验",
        "opening_style": "谦虚好学，主动提问"
    },
    "带组专家": {
        "name": "李教授",
        "title": "带组专家",
        "difficulty": 5,
        "strictness": 0.9,
        "personality": "影响力型、决策权高，一言九鼎，注重品牌和口碑",
        "opening_style": "威严但礼貌，试探对方实力"
    }
}

# ============ 对话场景配置 ============
DIALOGUE_SCENARIOS = [
    {
        "round": 1,
        "topic": "开场建立关系",
        "goal": "建立信任，了解医生对子宫内膜异位症的诊疗观点",
        "key_points": ["礼貌问候", "了解现状", "寻找痛点"],
        "opening": "你好，请问有什么事吗？"
    },
    {
        "round": 2,
        "topic": "产品引入",
        "goal": "自然引入维宝宁，引起医生兴趣",
        "key_points": ["产品定位", "核心优势", "差异化特点"],
        "opening": "说到产品，维宝宁在这方面有什么特点？"
    },
    {
        "round": 3,
        "topic": "机制与循证",
        "goal": "阐述维宝宁的作用机制和临床证据",
        "key_points": ["作用机制", "临床数据", "指南推荐"],
        "opening": "维宝宁的具体作用机制是什么？有相关的临床数据支持吗？"
    },
    {
        "round": 4,
        "topic": "临床应用",
        "goal": "探讨维宝宁在具体临床场景中的应用",
        "key_points": ["适用人群", "用药时机", "联合用药"],
        "opening": "在实际临床中，维宝宁适合哪些患者使用？"
    },
    {
        "round": 5,
        "topic": "安全性与耐受性",
        "goal": "解答医生对药物安全性的顾虑",
        "key_points": ["不良反应", "禁忌症", "特殊人群"],
        "opening": "患者比较关心药物的安全性，维宝宁在这方面的表现如何？"
    },
    {
        "round": 6,
        "topic": "竞品对比",
        "goal": "客观比较维宝宁与竞品的差异",
        "key_points": ["与GnRH对比", "与避孕药对比", "与手术对比"],
        "opening": "相比其他治疗方案，维宝宁有什么独特之处？"
    },
    {
        "round": 7,
        "topic": "处理异议",
        "goal": "有效应对医生的疑虑和反对意见",
        "key_points": ["价格异议", "疗效质疑", "使用习惯"],
        "opening": "有些医生觉得维宝宁价格偏高，你怎么看待这个问题？"
    },
    {
        "round": 8,
        "topic": "达成共识与后续",
        "goal": "促成试用或进一步交流",
        "key_points": ["试用邀请", "资料提供", "后续跟进"],
        "opening": "基于我们今天的交流，您愿意让合适的患者试用维宝宁吗？"
    }
]

# ============ 核心函数：判断是否推进到下一轮 ============
def should_advance_round(doctor_reply, exchange_count):
    """
    判断是否应该推进到下一轮
    
    逻辑：
    1. 最多3轮强制推进（追问2次后必须推进）
    2. 只有医生明确添加【推进到下一轮】标记时才推进
    """
    # 最多3轮强制推进（追问2次后必须推进）
    if exchange_count >= 3:
        return True
    
    # 只有医生明确添加【推进到下一轮】标记时才推进
    if "【推进到下一轮】" in doctor_reply:
        return True
    
    # 其他情况不推进，继续本轮追问
    return False


# ============ 核心函数：生成医生回复 ============
def generate_doctor_reply(user_message, session, current_round):
    """使用智谱AI生成医生回复"""
    
    doctor_type = session["doctor_type"]
    doctor = DOCTOR_PROFILES[doctor_type]
    scenario = DIALOGUE_SCENARIOS[current_round - 1]
    round_data = session["current_round_data"]
    exchange_count = round_data["exchange_count"]
    
    # 构建对话历史
    history = ""
    for msg in round_data["messages"]:
        if msg["role"] == "user":
            history += f"医药代表：{msg['content']}\n"
        else:
            history += f"{doctor['name']}：{msg['content']}\n"
    
    # 判断用户回答质量
    user_answer_quality = "good"
    if len(user_message) < 30:
        user_answer_quality = "poor"
    elif "这个" in user_message and "那个" in user_message:
        user_answer_quality = "vague"
    
    # 医生系统提示词
    system_prompt = f"""你是{doctor['title']} {doctor['name']}，正在接待医药代表拜访。

【你的性格】
{doctor['personality']}
说话风格：简短有力（30-60字），像真实医生说话，不要长篇大论。

【当前场景】
第{current_round}轮/共8轮：{scenario['topic']}
目标：{scenario['goal']}

【本轮对话历史】
{history}
医药代表：{user_message}

【用户回答质量】
{user_answer_quality}

【关键规则】
1. 判断用户回答质量：
   - 质量差（短/模糊/敷衍）→ 必须追问，要求详细说明
   - 质量好（完整清晰）→ 可以简短认可，然后推进
2. 追问时：直接提出具体问题，不要加【推进到下一轮】
3. 推进时：必须添加【推进到下一轮】标记，否则系统不会推进
4. 最多追问2次（第3次必须推进）
5. 回复必须简短（30-60字），像真实医生说话

【回复示例】
- 追问（质量差）："具体是什么情况？" / "能详细说说吗？" / "数据呢？"
- 推进（质量好）："了解了。说到{scenario['topic']}，维宝宁有什么特点？【推进到下一轮】"

【格式要求】
直接回复医生的话，不要加任何前缀、解释或"医生说："。"""

    # 调用智谱AI
    if ZHIPU_API_KEY:
        try:
            import requests
            url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
            headers = {
                "Authorization": f"Bearer {ZHIPU_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "glm-4",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                "temperature": 0.7,
                "max_tokens": 100,
                "top_p": 0.9
            }
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            result = response.json()
            if "choices" in result and len(result["choices"]) > 0:
                reply = result["choices"][0]["message"]["content"].strip()
                # 清理回复
                reply = reply.replace(f"{doctor['name']}：", "").replace(f"{doctor['title']}：", "")
                reply = reply.strip('"')
                return reply
        except Exception as e:
            print(f"Zhipu API error: {e}")
    
    # 备用回复逻辑（当API不可用时）
    return generate_fallback_reply(user_message, doctor, scenario, exchange_count, user_answer_quality)

def generate_fallback_reply(user_message, doctor, scenario, exchange_count, user_answer_quality):
    """当AI API不可用时使用的备用回复"""
    
    # 如果用户回答质量差，追问
    if user_answer_quality in ["poor", "vague"] and exchange_count < 3:
        follow_ups = [
            "能具体说说吗？",
            "详细一点。",
            "数据呢？",
            "举个例子。"
        ]
        return follow_ups[exchange_count % len(follow_ups)]
    
    # 如果已经对话2次以上，推进
    if exchange_count >= 2:
        # 必须包含过渡词 + 问句 + 【推进到下一轮】
        transitions = [
            f"了解了。说到{scenario['topic']}，维宝宁在这方面有什么特点？【推进到下一轮】",
            f"知道了。那关于{scenario['topic']}，维宝宁有什么具体优势？【推进到下一轮】",
            f"明白了。说到产品，维宝宁在{scenario['topic']}上表现如何？【推进到下一轮】"
        ]
        return transitions[exchange_count % len(transitions)]
    
    # 默认继续
    continues = ["嗯。", "继续。", "还有呢？"]
    return continues[exchange_count % len(continues)]



def evaluate_round(session, current_round, user_message="", doctor_reply=""):
    """
    评估本轮对话表现 - 新评分维度（总分10分）
    
    评分维度：
    - 内容准确性：0-3分（信息是否正确、专业）
    - 表达清晰度：0-2分（逻辑是否清晰、易懂）
    - 客户需求匹配：0-2分（是否回应医生关切）
    - 专业度：0-2分（是否体现专业素养）
    - 加分项：0-1分（超出预期的亮点）
    - 追问惩罚：被追问1次-0.5分，2次-1分，3次-2分
    """
    
    round_data = session["current_round_data"]
    exchange_count = round_data["exchange_count"]
    doctor_type = session["doctor_type"]
    doctor = DOCTOR_PROFILES[doctor_type]
    scenario = DIALOGUE_SCENARIOS[current_round - 1]
    
    # 基础评分（根据回答质量）
    message_length = len(user_message)
    
    # 内容准确性（0-3分）
    if message_length > 100:
        accuracy = 2.5
    elif message_length > 50:
        accuracy = 2.0
    elif message_length > 30:
        accuracy = 1.5
    else:
        accuracy = 1.0
    
    # 表达清晰度（0-2分）
    clarity = 1.5 if message_length > 50 else 1.0
    
    # 客户需求匹配（0-2分）
    match = 1.5 if message_length > 50 else 1.0
    
    # 专业度（0-2分）
    professionalism = 1.5 if message_length > 50 else 1.0
    
    # 加分项（0-1分）
    bonus = 0.5 if message_length > 100 else 0
    
    # 追问惩罚
    if exchange_count == 1:
        penalty = 0
    elif exchange_count == 2:
        penalty = 0.5
    elif exchange_count == 3:
        penalty = 1.0
    else:
        penalty = 2.0
    
    # 计算总分
    total_score = accuracy + clarity + match + professionalism + bonus - penalty
    
    # 根据实际得分给出反馈（不是根据追问次数）
    if total_score >= 8:
        feedback = "回答优秀！内容准确、表达清晰，很好地回应了医生的关切。"
    elif total_score >= 6:
        feedback = "回答良好，基本达到了预期，但还有提升空间。"
    elif total_score >= 4:
        feedback = "回答一般，需要更准确地把握医生需求，提高信息完整性。"
    else:
        feedback = "回答需要改进，建议加强产品知识学习，提高表达能力。"

    
    # 生成 strengths 和 improvements
    strengths = []
    improvements = []
    
    if accuracy >= 2.5:
        strengths.append("内容准确专业")
    else:
        improvements.append("提高内容准确性")
        
    if clarity >= 1.5:
        strengths.append("表达清晰易懂")
    else:
        improvements.append("增强表达清晰度")
        
    if penalty == 0:
        strengths.append("一次性回答到位")
    else:
        improvements.append("减少被追问次数")
    
    return {
        "round": current_round,
        "topic": scenario['topic'],
        "score": round(total_score, 1),
        "exchange_count": exchange_count,
        "details": {
            "内容准确性": accuracy,
            "表达清晰度": clarity,
            "客户需求匹配": match,
            "专业度": professionalism,
            "加分项": bonus,
            "追问惩罚": -penalty
        },
        "feedback": feedback,
        "strengths": strengths,
        "improvements": improvements
    }

def generate_summary(session_data):
    """生成总结报告"""
    
    evaluations = session_data.get("evaluations", [])
    total_score = sum(e.get("score", 0) for e in evaluations)
    max_score = len(evaluations) * 10 if evaluations else 80
    avg_score = total_score / len(evaluations) if evaluations else 0
    
    doctor = DOCTOR_PROFILES[session_data["doctor_type"]]
    
    if avg_score >= 9:
        level = "优秀"
        level_emoji = "🏆"
    elif avg_score >= 7.5:
        level = "良好"
        level_emoji = "👍"
    elif avg_score >= 6:
        level = "及格"
        level_emoji = "📖"
    else:
        level = "需改进"
        level_emoji = "💪"
    
    summary = f"""{level_emoji} 拜访演练总结报告

📊 总体表现
• 医生角色：{doctor['title']} {doctor['name']}
• 难度等级：{"⭐" * doctor['difficulty']}
• 总得分：{total_score:.1f}/{max_score}
• 平均分：{avg_score:.1f}/10
• 综合评级：{level}

📝 各轮表现
"""
    
    for i, eval_data in enumerate(evaluations, 1):
        scenario = DIALOGUE_SCENARIOS[i-1]
        score = eval_data.get('score', 0)
        stars = "⭐" * int(score // 2)
        if score % 2 >= 1:
            stars += "✨"
        
        summary += f"""
第{i}轮：{scenario['topic']}
得分：{score}/10 {stars}
对话次数：{eval_data.get('exchange_count', 1)}次
评价：{eval_data.get('feedback', '无')[:60]}...
"""
    
    all_strengths = []
    all_improvements = []
    for e in evaluations:
        all_strengths.extend(e.get('strengths', []))
        all_improvements.extend(e.get('improvements', []))
    
    unique_strengths = list(dict.fromkeys(all_strengths))[:3]
    unique_improvements = list(dict.fromkeys(all_improvements))[:3]
    
    summary += """
💡 总体建议

继续保持：
"""
    for s in unique_strengths:
        summary += f"• {s}\n"
    
    summary += """
重点提升：
"""
    for i in unique_improvements:
        summary += f"• {i}\n"
    
    summary += f"""
下次目标：争取总分达到 {min(total_score + 15, max_score):.1f} 分以上

生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""
    
    return summary


# ============ 飞书消息发送 ============
def send_feishu_message(open_id, user_id, reply_text):
    """发送飞书消息"""
    try:
        token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        token_resp = requests.post(
            token_url,
            json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET},
            timeout=10
        )
        token_data = token_resp.json()
        
        token = token_data.get("tenant_access_token")
        if not token:
            print(f"Failed to get token: {token_data}")
            return
        
        send_url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        receive_id = open_id if open_id else user_id
        
        # 清理回复中的标记
        clean_reply = reply_text.replace("【推进到下一轮】", "")
        
        max_length = 3000
        if len(clean_reply) > max_length:
            parts = [clean_reply[i:i+max_length] for i in range(0, len(clean_reply), max_length)]
            for part in parts:
                payload = {
                    "receive_id": receive_id,
                    "content": json.dumps({"text": part}, ensure_ascii=False),
                    "msg_type": "text"
                }
                requests.post(send_url, headers=headers, json=payload, timeout=10)
        else:
            payload = {
                "receive_id": receive_id,
                "content": json.dumps({"text": clean_reply}, ensure_ascii=False),
                "msg_type": "text"
            }
            requests.post(send_url, headers=headers, json=payload, timeout=10)
    
    except Exception as e:
        print(f"Send feishu message error: {e}")


def process_message_async(open_id, user_id, text, message_id):
    """异步处理消息"""
    try:
        # 先检查是否已处理（内存 + 文件）
        if message_id in processed_messages:
            print(f"Message {message_id} already processed (memory)")
            return
        
        # 再次检查文件（防止多线程竞争）
        try:
            if os.path.exists(PROCESSED_MESSAGES_FILE):
                with open(PROCESSED_MESSAGES_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if message_id in data:
                        print(f"Message {message_id} already processed (file)")
                        return
        except:
            pass
        
        # 添加到内存集合
        processed_messages.add(message_id)
        
        # 持久化到文件
        save_processed_message(message_id)
        
        reply_text = generate_reply(open_id, user_id, text)
        
        # 确保有回复内容
        if not reply_text:
            reply_text = "抱歉，系统处理出错，请发送'开始'重新训练。"
        
        send_feishu_message(open_id, user_id, reply_text)
    except Exception as e:
        print(f"ERROR in process_message_async: {e}")
        import traceback
        traceback.print_exc()
        # 尝试发送错误信息
        try:
            send_feishu_message(open_id, user_id, f"系统错误: {str(e)[:50]}。请发送'开始'重新训练。")
        except:
            pass


# ============ 核心函数：生成回复 ============
def generate_reply(open_id, user_id, text):
    """生成回复（核心逻辑）"""
    try:
        return _do_generate_reply(open_id, user_id, text)
    except Exception as e:
        print(f"ERROR in generate_reply: {e}")
        import traceback
        traceback.print_exc()
        return f"系统错误: {str(e)[:50]}。请发送'开始'重新训练。"

def _do_generate_reply(open_id, user_id, text):
    """实际生成回复"""
    
    # 开始指令
    if text in ["/start", "开始", "开始训练", "开始练习"]:
        reply_text = """🎯 请选择医生角色开始训练：

1️⃣ 主任级专家 ⭐⭐⭐⭐⭐
   学术型、严谨、注重循证医学证据

2️⃣ 科室主任 ⭐⭐⭐⭐
   管理型、务实、关注科室效益

3️⃣ 主治医师 ⭐⭐⭐
   实用型、经验导向

4️⃣ 住院医师 ⭐⭐
   学习型、听从上级

5️⃣ 带组专家 ⭐⭐⭐⭐⭐
   影响力型、决策权高

请回复数字 1-5 选择医生"""
        user_sessions[user_id] = "selecting_doctor"
        return reply_text
    
    # 医生选择
    elif text in ["1", "2", "3", "4", "5"] and user_sessions.get(user_id) == "selecting_doctor":
        doctor_map = {"1": "主任级专家", "2": "科室主任", "3": "主治医师", "4": "住院医师", "5": "带组专家"}
        doctor_type = doctor_map.get(text, "副主任医师")
        
        session_id = str(uuid.uuid4())
        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "doctor_type": doctor_type,
            "current_round": 1,
            "current_round_data": {
                "exchange_count": 0,
                "messages": [],
                "evaluated": False
            },
            "evaluations": [],
            "start_time": datetime.now().isoformat(),
            "status": "active"
        }
        sessions[session_id] = session_data
        user_sessions[user_id] = session_id
        
        scenario = DIALOGUE_SCENARIOS[0]
        doctor = DOCTOR_PROFILES[doctor_type]
        opening = scenario['opening']
        
        session_data["current_round_data"]["messages"].append({
            "role": "doctor",
            "content": opening
        })
        
        return f"""🎯 销售话术对练开始！

👨‍⚕️ 医生角色：{doctor['title']} {doctor['name']}
难度：{'⭐' * doctor['difficulty']}

{doctor['name']}：{opening}

💡 第1轮/共8轮：{scenario['topic']}
🎯 目标：{scenario['goal']}"""
    
    # 帮助
    elif text in ["/help", "帮助", "?", "？"]:
        return """🎯 维宝宁销售培训机器人

【训练说明】
• 共8轮对话，每轮可以有多轮交流
• 医生会根据你的回答质量决定是否追问
• 每轮结束给一次评分（满分10分，支持0.5分）
• 追问次数会影响评分（被追问越多，扣分越多）
• 完成后生成总结报告

发送「开始」即可开始训练！"""
    
    # 检查是否正在选择医生
    elif user_sessions.get(user_id) == "selecting_doctor":
        return "请选择医生：回复 1-5 选择医生角色"
    
    # 检查是否有活跃会话
    elif user_id in user_sessions:
        session_id = user_sessions[user_id]
        
        if session_id in ["selecting_doctor", None]:
            return "会话异常，请发送「开始」重新开始"
        
        if session_id not in sessions:
            del user_sessions[user_id]
            return "会话已过期，请发送「开始」重新开始"
        
        session = sessions[session_id]
        current_round = session["current_round"]
        round_data = session["current_round_data"]
        
        if current_round > 8:
            summary = generate_summary(session)
            del user_sessions[user_id]
            return summary + "\n\n🎉 训练结束！发送「开始」可重新练习。"
        
        # 记录用户消息
        round_data["exchange_count"] += 1
        round_data["messages"].append({
            "role": "user",
            "content": text,
            "exchange": round_data["exchange_count"]
        })
        
        # 生成医生回复
        doctor_reply = generate_doctor_reply(text, session, current_round)
        
        # 记录医生回复
        round_data["messages"].append({
            "role": "doctor",
            "content": doctor_reply,
            "exchange": round_data["exchange_count"]
        })
        
        # 判断是否推进到下一轮
        should_advance = should_advance_round(doctor_reply, round_data["exchange_count"])
        
        if should_advance:
            # 评估本轮表现
            evaluation = evaluate_round(session, current_round, text, doctor_reply)
            session["evaluations"].append(evaluation)
            
            # 清理医生回复中的标记
            clean_doctor_reply = doctor_reply.replace("【推进到下一轮】", "").strip()
            
            # 准备下一轮
            session["current_round"] = current_round + 1
            session["current_round_data"] = {
                "exchange_count": 0,
                "messages": [],
                "evaluated": False
            }
            
            if current_round == 8:
                # 结束
                summary = generate_summary(session)
                del user_sessions[user_id]
                score = evaluation.get('score', 0)
                feedback = evaluation.get('feedback', '')[:80]
                
                return f"""👨‍⚕️ {clean_doctor_reply}

📊 第8轮评分：{score}/10
💬 反馈：{feedback}

{summary}

🎉 训练结束！发送「开始」可重新练习。"""
            else:
                # 进入下一轮 - 一句话自然过渡
                next_round = session["current_round"]
                next_scenario = DIALOGUE_SCENARIOS[next_round - 1]
                score = evaluation.get('score', 0)
                feedback = evaluation.get('feedback', '')[:80]
                
                return f"""👨‍⚕️ {clean_doctor_reply}

📊 第{current_round}轮评分：{score}/10
💬 反馈：{feedback}

💡 第{next_round}轮/共8轮：{next_scenario['topic']}
🎯 目标：{next_scenario['goal']}"""
        else:
            # 继续本轮
            scenario = DIALOGUE_SCENARIOS[current_round - 1]
            exchange_info = f"（第{round_data['exchange_count']}次对话）" if round_data['exchange_count'] > 1 else ""
            
            # 清理医生回复中的标记
            clean_doctor_reply = doctor_reply.replace("【推进到下一轮】", "").strip()
            
            return f"""👨‍⚕️ {clean_doctor_reply}

💡 第{current_round}轮/共8轮：{scenario['topic']} {exchange_info}
🎯 目标：{scenario['goal']}"""
    
    else:
        return "请先发送「开始」或「/start」开始训练"


# ============ 飞书适配接口 ============
@app.route("/webhook/feishu", methods=["POST"])
def feishu_webhook():
    """处理飞书消息 - 兼容 /webhook/feishu 路径"""
    return feishu_chat()

@app.route("/api/feishu/chat", methods=["POST"])
def feishu_chat():
    """处理飞书消息 - 立即返回，异步处理"""
    raw_data = request.get_data(as_text=True)
    data = json.loads(raw_data) if raw_data else {}
    
    if "challenge" in data:
        return jsonify({"challenge": data["challenge"]})
    
    event = data.get("event", {})
    message = event.get("message", {})
    sender = event.get("sender", {})
    sender_id = sender.get("sender_id", {})
    user_id = sender_id.get("user_id", "")
    open_id = sender_id.get("open_id", "")
    message_id = message.get("message_id", "")
    
    content_str = message.get("content", "{}")
    try:
        content = json.loads(content_str) if isinstance(content_str, str) else content_str
    except:
        content = {}
    text = content.get("text", "").strip()
    
    # 检查是否已处理（内存 + 文件）
    if message_id in processed_messages:
        print(f"Duplicate message blocked (memory): {message_id}")
        return jsonify({"code": 0, "msg": "success"})
    
    # 再次检查文件（防止服务重启后内存丢失）
    try:
        if os.path.exists(PROCESSED_MESSAGES_FILE):
            with open(PROCESSED_MESSAGES_FILE, 'r', encoding='utf-8') as f:
                file_data = json.load(f)
                if message_id in file_data:
                    print(f"Duplicate message blocked (file): {message_id}")
                    # 同步到内存
                    processed_messages.add(message_id)
                    return jsonify({"code": 0, "msg": "success"})
    except Exception as e:
        print(f"Error checking processed messages file: {e}")
    
    thread = threading.Thread(
        target=process_message_async,
        args=(open_id, user_id, text, message_id)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({"code": 0, "msg": "success"})


# ============ API路由（供网页/其他系统使用） ============
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
        "current_round_data": {
            "exchange_count": 0,
            "messages": [],
            "evaluated": False
        },
        "evaluations": [],
        "start_time": datetime.now().isoformat(),
        "status": "active"
    }
    sessions[session_id] = session_data
    
    scenario = DIALOGUE_SCENARIOS[0]
    doctor = DOCTOR_PROFILES[doctor_type]
    opening = scenario['opening']
    
    session_data["current_round_data"]["messages"].append({
        "role": "doctor",
        "content": opening
    })
    
    return jsonify({
        "session_id": session_id,
        "message": f"{doctor['name']}：{opening}",
        "round": 1,
        "topic": scenario['topic'],
        "goal": scenario['goal']
    })


@app.route("/api/chat", methods=["POST"])
def chat():
    """处理对话（API版本）"""
    data = request.json or {}
    session_id = data.get("session_id")
    user_message = data.get("message", "")
    
    if not session_id or session_id not in sessions:
        return jsonify({"error": "会话不存在"}), 400
    
    session = sessions[session_id]
    current_round = session["current_round"]
    round_data = session["current_round_data"]
    
    if current_round > 8:
        return jsonify({"error": "对话已完成"}), 400
    
    round_data["exchange_count"] += 1
    round_data["messages"].append({
        "role": "user",
        "content": user_message,
        "exchange": round_data["exchange_count"]
    })
    
    doctor_reply = generate_doctor_reply(user_message, session, current_round)
    
    round_data["messages"].append({
        "role": "doctor",
        "content": doctor_reply,
        "exchange": round_data["exchange_count"]
    })
    
    should_advance = should_advance_round(doctor_reply, round_data["exchange_count"])
    
    result = {
        "session_id": session_id,
        "round": current_round,
        "doctor_reply": doctor_reply.replace("【推进到下一轮】", "").strip(),
        "exchange_count": round_data["exchange_count"],
        "advanced": should_advance
    }
    
    if should_advance:
        evaluation = evaluate_round(session, current_round)
        session["evaluations"].append(evaluation)
        
        result["evaluation"] = evaluation
        
        session["current_round"] = current_round + 1
        session["current_round_data"] = {
            "exchange_count": 0,
            "messages": [],
            "evaluated": False
        }
        
        if current_round == 8:
            session["status"] = "completed"
            result["completed"] = True
            result["summary"] = generate_summary(session)
        else:
            next_scenario = DIALOGUE_SCENARIOS[session["current_round"] - 1]
            result["next_topic"] = next_scenario["topic"]
            result["next_goal"] = next_scenario["goal"]
    
    return jsonify(result)


@app.route("/api/summary/<session_id>", methods=["GET"])
def get_summary(session_id):
    """获取总结报告"""
    if session_id not in sessions:
        return jsonify({"error": "会话不存在"}), 404
    
    session = sessions[session_id]
    summary = generate_summary(session)
    
    return jsonify({
        "session_id": session_id,
        "summary": summary,
        "evaluations": session.get("evaluations", [])
    })


@app.route("/api/doctors", methods=["GET"])
def list_doctors():
    """获取可选医生角色"""
    doctors = []
    for key, profile in DOCTOR_PROFILES.items():
        doctors.append({
            "type": key,
            "name": profile["name"],
            "title": profile["title"],
            "difficulty": profile["difficulty"],
            "strictness": profile["strictness"]
        })
    
    return jsonify({"doctors": doctors})


# ============ 其他路由 ============
@app.route("/")
def index():
    return "维宝宁销售培训机器人 - 运行正常"


@app.route("/health")
def health():
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})


# ============ 主入口 ============
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
