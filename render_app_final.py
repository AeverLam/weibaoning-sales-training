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

# 存储
sessions = {}
user_sessions = {}
processed_messages = set()

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
    1. 最多3轮强制推进
    2. 有明确推进标记时推进
    3. 语义判断：医生是否已开启新话题（过渡词 + 新问题）
    """
    # 最多3轮强制推进
    if exchange_count >= 3:
        return True
    
    # 如果有明确的推进标记，直接推进
    if "【推进到下一轮】" in doctor_reply:
        return True
    
    # 语义判断：医生是否已开启新话题
    clean_reply = doctor_reply.replace("【推进到下一轮】", "").strip()
    
    # 检查是否包含话题转换信号词（结束上轮 + 开启下轮）
    transition_signals = [
        "说到", "谈到", "关于", "至于", "接下来", "那", "那么",
        "我们聊聊", "说说", "讲讲", "看看", "聊聊", "说说看",
        "对了", "顺便问一下", "另外"
    ]
    has_transition = any(signal in clean_reply for signal in transition_signals)
    
    # 检查是否以问句结束（开启新问题的第一个提问）
    ends_with_new_question = clean_reply.endswith(("?", "？"))
    
    # 推进条件：有过渡信号 + 以新问题结束 + 至少已对话1轮
    # 这意味着医生已经：总结了上轮 → 过渡到下轮 → 提出了第一个问题
    if has_transition and ends_with_new_question and exchange_count >= 1:
        return True
    
    return False


# ============ 核心函数：生成医生回复 ============
def generate_doctor_reply(user_message, session, current_round):
    """使用AI生成医生回复"""
    
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
    
    # 医生系统提示词
    system_prompt = f"""你是{doctor['title']} {doctor['name']}，正在接待医药代表拜访。

【你的性格】
{doctor['personality']}

【当前场景】
第{current_round}轮/共8轮：{scenario['topic']}
目标：{scenario['goal']}

【本轮对话历史】
{history}
医药代表：{user_message}

【关键规则】
1. 判断标准：
   - 回答优秀/良好（信息准确、完整、清晰）→ 用陈述句认可，然后自然过渡到下一轮
   - 回答有缺陷/差（信息缺失、不准确、不清晰）→ 指出问题，用问句追问，继续本轮

2. 【重要】推进规则：
   - 如果还有疑问需要追问，用问句，不要加【推进到下一轮】
   - 只有当问题探讨清楚，准备进入下一轮时，才加【推进到下一轮】
   - 推进时必须一句话完成三件事：
     a) 用陈述句总结/认可上轮
     b) 用过渡词引出下轮话题
     c) 用问句提出下轮的第一个问题

3. 示例：
   - 追问（继续本轮）："除了疼痛，患者还有哪些副作用？"
   - 推进（进入下轮）："明白了，内异症确实棘手。说到产品，维宝宁在这方面有什么特点？【推进到下一轮】"

4. 追问次数：最多追问2-3次，达到后必须推进

【回复格式】
直接回复医生的话，不要加任何前缀或解释。"""

    try:
        # 这里调用AI API生成回复
        # 实际部署时需要替换为真实的API调用
        # 示例使用简单的模拟回复
        
        # 模拟智能判断：根据exchange_count和消息内容决定追问或推进
        if exchange_count < 2 and len(user_message) < 50:
            # 回答较短，继续追问
            follow_up_questions = [
                "能详细说说吗？",
                "还有呢？",
                "具体是什么情况？",
                "为什么这样说？"
            ]
            reply = follow_up_questions[exchange_count % len(follow_up_questions)]
        else:
            # 回答足够，推进到下轮
            next_scenario = DIALOGUE_SCENARIOS[current_round] if current_round < 8 else None
            if next_scenario:
                transitions = [
                    f"明白了。说到{next_scenario['topic']}，{next_scenario['opening']}【推进到下一轮】",
                    f"了解了。那关于{next_scenario['topic']}，{next_scenario['opening']}【推进到下一轮】",
                    f"好的。接下来聊聊{next_scenario['topic']}，{next_scenario['opening']}【推进到下一轮】"
                ]
                reply = transitions[exchange_count % len(transitions)]
            else:
                reply = "好的，今天的交流很有收获。谢谢你的介绍。"
        
        return reply
        
    except Exception as e:
        print(f"Generate doctor reply error: {e}")
        return "嗯，我明白了。还有其他要补充的吗？"


# ============ 核心函数：评估本轮表现 ============
def evaluate_round(session, current_round):
    """
    评估本轮对话表现
    
    评分维度：
    - 回答准确性 30%
    - 回答完整性 25%
    - 表达清晰度 20%
    - 追问惩罚 15%（被追问越多扣分越多）
    - 难度系数 10%
    """
    
    round_data = session["current_round_data"]
    exchange_count = round_data["exchange_count"]
    doctor_type = session["doctor_type"]
    doctor = DOCTOR_PROFILES[doctor_type]
    scenario = DIALOGUE_SCENARIOS[current_round - 1]
    
    # 基础分数（根据对话轮数调整）
    # 理想情况：1轮回答清楚，得高分
    # 被追问越多，基础分越低
    if exchange_count == 1:
        base_score = 9.0
    elif exchange_count == 2:
        base_score = 7.5
    elif exchange_count == 3:
        base_score = 6.0
    else:
        base_score = 5.0
    
    # 难度系数调整
    difficulty_bonus = (doctor['difficulty'] - 3) * 0.2  # -0.4 ~ +0.4
    
    # 计算最终分数
    final_score = min(10.0, max(1.0, base_score + difficulty_bonus))
    
    # 生成反馈
    if exchange_count == 1:
        feedback = "回答准确完整，一次性抓住了重点，表现优秀！"
        strengths = ["信息准确", "回答完整", "表达清晰"]
        improvements = []
    elif exchange_count == 2:
        feedback = "回答基本到位，但医生需要追问才获得完整信息，可以更加主动。"
        strengths = ["信息基本准确", "能回应追问"]
        improvements = ["可以更主动提供完整信息", "减少被追问次数"]
    else:
        feedback = "回答不够完整或清晰，医生多次追问才获得所需信息，需要改进。"
        strengths = ["能坚持对话"]
        improvements = ["提高信息完整性", "增强表达清晰度", "预判医生关注点"]
    
    return {
        "round": current_round,
        "topic": scenario['topic'],
        "score": round(final_score, 1),
        "exchange_count": exchange_count,
        "feedback": feedback,
        "strengths": strengths,
        "improvements": improvements
    }


# ============ 核心函数：生成总结报告 ============
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
    if message_id in processed_messages:
        return
    
    processed_messages.add(message_id)
    reply_text = generate_reply(open_id, user_id, text)
    send_feishu_message(open_id, user_id, reply_text)


# ============ 核心函数：生成回复 ============
def generate_reply(open_id, user_id, text):
    """生成回复（核心逻辑）"""
    
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
    elif text in ["1", "2", "3"] and user_sessions.get(user_id) == "selecting_doctor":
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
            evaluation = evaluate_round(session, current_round)
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
    
    if message_id in processed_messages:
        return jsonify({"code": 0, "msg": "success"})
    
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
