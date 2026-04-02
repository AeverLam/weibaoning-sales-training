#!/usr/bin/env python3 
-*- coding: utf-8 -*- 
""" 
维宝宁销售话术对练 - AI智能版 
使用LLM生成医生回复、实时评估 
""" 
import json 
import os 
import threading 
import requests 
from flask import Flask, request, jsonify 
 
app = Flask(__name__)
 
FEISHU_APP_ID = os.environ.get('FEISHU_APP_ID', 'cli_a938ac2a24391bcb') 
FEISHU_APP_SECRET = os.environ.get('FEISHU_APP_SECRET', '') 
 
# 内存存储
user_sessions = {} 
 
ROLES = {
    '1': ('主任级专家', '学术型', '⭐⭐⭐⭐⭐'),
    '2': ('科室主任', '管理型', '⭐⭐⭐⭐'),
    '3': ('主治医师', '实用型', '⭐⭐⭐'),
    '4': ('住院医师', '学习型', '⭐⭐'),
    '5': ('带组专家', '影响力型', '⭐⭐⭐⭐⭐') 
} 
 
# 医生角色设定
DOCTOR_PROFILES = {
    '主任级专家': {
        '性格': '严谨、学术导向、注重证据',
        '关注点': ['III期临床数据', '指南推荐', '长期安全性'],
        '说话风格': '专业、直接、爱追问数据'
    },
    '科室主任': {
        '性格': '务实、管理导向、关注性价比',
        '关注点': ['医保报销', '患者依从性', '科室效益'],
        '说话风格': '简洁、关注实际效果'
    },
    '主治医师': {
        '性格': '实用导向、经验主义',
        '关注点': ['使用便利性', '患者反馈', '竞品对比'],
        '说话风格': '随和、注重实用'
    } 
} 
 
def get_token():
    """获取飞书tenant_access_token"""
    try:
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        resp = requests.post(url, json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}, timeout=10)
        return resp.json().get("tenant_access_token")
    except:
        return None 
 
def send_msg(open_id, msg_id, text):
    """发送消息到飞书"""
    def do():
        try:
            token = get_token()
            if not token:
                return
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            if msg_id:
                url = f"https://open.feishu.cn/open-apis/im/v1/messages/{msg_id}/reply"
                data = {"msg_type": "text", "content": json.dumps({"text": text})}
            else:
                url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"
                data = {"receive_id": open_id, "msg_type": "text", "content": json.dumps({"text": text})}
            requests.post(url, headers=headers, json=data, timeout=10)
        except:
            pass
    threading.Thread(target=do, daemon=True).start()


def call_llm(messages):
    """调用LLM生成回复"""
    try:
        api_key = os.environ.get('MINIMAX_API_KEY', '')
        if not api_key:
            return None 

        url = "https://api.minimax.chat/v1/text/chatcompletion_v2"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        } 

        payload = {
            "model": "abab6.5-chat",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 150
        } 

        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        result = resp.json() 

        if 'choices' in result and len(result['choices']) > 0:
            return result['choices'][0]['message']['content']
        return None
    except Exception as e:
        print(f"LLM error: {e}")
        return None 
 
def generate_doctor_response(user_message, doctor_type, round_num, history):
    """使用LLM生成医生回复"""
    profile = DOCTOR_PROFILES.get(doctor_type, DOCTOR_PROFILES['科室主任']) 

    system_prompt = f"""你是一位{doctor_type}，{profile['性格']}。 
你最关注：{', '.join(profile['关注点'])}。 
你的说话风格：{profile['说话风格']}。 
 
你正在和一位医药代表对话，这是第{round_num}轮。 
请根据对方的回答，自然地回应，保持角色一致性。 
回复控制在2-3句话，不要太长。 
 
维宝宁产品信息： 
- 通用名：注射用醋酸亮丙瑞林微球 
- 适应症：子宫内膜异位症 
- 特点：E2去势率97.45%，妊娠率87.3% 
- 价格：约1000元/支""" 
    messages = [{"role": "system", "content": system_prompt}] 
    # 添加历史对话 
    for h in history[-3:]:
        messages.append({"role": "user", "content": h.get('user', '')})
        messages.append({"role": "assistant", "content": h.get('doctor', '')}) 

    messages.append({"role": "user", "content": user_message}) 

    response = call_llm(messages)
    if response:
        return response 
     
    # LLM失败时的备用回复 
    fallback = [
        "嗯，这个产品我之前没怎么了解过。",
        "你说说看，有什么临床数据支持？",
        "价格怎么样？患者能接受吗？",
        "副作用大不大？",
        "如果效果好，可以考虑试试。"
    ]
    return fallback[min(round_num - 1, len(fallback) - 1)] 
 
def evaluate_response(user_message, doctor_type, round_num):
    """评估用户回答质量"""
    score = 6
    strengths = []
    weaknesses = [] 
     
    # 关键词检查 
    keywords = {
        'product': ['E2', '去势率', '97%', '微球', '亮丙瑞林', '妊娠率', '87.3%'],
        'technique': ['优势', '特点', '效果', '数据', '临床'],
        'communication': ['您', '主任', '感谢', '打扰']
    } 

    for category, words in keywords.items():
        matches = sum(1 for w in words if w in user_message)
        if matches >= 2:
            score += 1
            if category == 'product':
                strengths.append("产品知识扎实")
            elif category == 'technique':
                strengths.append("话术运用得当")
            elif category == 'communication':
                strengths.append("沟通礼仪得体") 

    score = min(score, 10) 

    if score >= 9:
        grade = 'A'
        feedback = "🌟 表现优秀！"
    elif score >= 7:
        grade = 'B'
        feedback = "👍 表现良好"
    elif score >= 5:
        grade = 'C'
        feedback = "💡 表现一般，还有提升空间"
    else:
        grade = 'D'
        feedback = "📝 需要改进" 

    if not strengths:
        weaknesses.append("建议多使用产品关键数据") 

    return {
        'score': score,
        'grade': grade,
        'feedback': feedback,
        'strengths': strengths,
        'weaknesses': weaknesses
    } 
 
def handle_msg(text, user_id, msg_id=None):
    """处理用户消息"""
    text = text.strip() 
     
    # 开始练习 
    if text in ['开始练习', 'start', '开始']:
        user_sessions[user_id] = {
            'step': 0,
            'role': None,
            'scores': [],
            'history': []
        }
        return "👋 欢迎开始维宝宁销售话术对练（AI智能版）！\n\n请选择医生角色（回复数字）：\n1️⃣ 主任级专家 ⭐⭐⭐⭐⭐\n2️⃣ 科室主任 ⭐⭐⭐⭐\n3️⃣ 主治医师 ⭐⭐⭐\n4️⃣ 住院医师 ⭐⭐\n5️⃣ 带组专家 ⭐⭐⭐⭐⭐" 
     
    # 结束练习 
    if text in ['结束', 'stop', '退出']:
        if user_id in user_sessions:
            del user_sessions[user_id]
        return "对练已结束。发送【开始练习】重新开始" 

    session = user_sessions.get(user_id)
    if not session:
        return "发送【开始练习】开始新的对练" 
     
    # 选择角色 
    if session['step'] == 0:
        if text in ROLES:
            role_name, role_type, stars = ROLES[text]
            session['role'] = role_name
            session['step'] = 1 
             
            # AI生成医生开场白 
            opening = generate_doctor_response(
                "你好，我是丽珠医药的代表，想介绍一下维宝宁。",
                role_name, 1, []
            ) 

            return f"✅ 已选择：{role_name} {stars}\n类型：{role_type}\n\n🎬 第1轮：开场白\n\n👨‍⚕️ 医生说：\"{opening}\"\n\n💬 请回复你的开场白..."
        return "请选择 1-5" 

    step = session['step']
    role = session['role'] 
     
    # 评估用户回答 
    evaluation = evaluate_response(text, role, step)
    session['scores'].append(evaluation) 
     
    # 记录历史 
    session['history'].append({
        'user': text,
        'doctor': '',
        'round': step
    }) 
     
    # 检查是否完成8轮 
    if step >= 8: 
        # 生成最终报告 
        scores = [s['score'] for s in session['scores']]
        avg = sum(scores) / len(scores) 
         
        # 生成等级 
        if avg >= 9:
            final_grade = 'A'
            feedback = "🏆 优秀！话术专业、逻辑清晰，充分展示了产品价值。"
        elif avg >= 7:
            final_grade = 'B'
            feedback = "🥈 良好！掌握了基本技巧，但在某些细节上可以更精进。"
        elif avg >= 5:
            final_grade = 'C'
            feedback = "🥉 及格！对产品有一定了解，但话术需要更加熟练。"
        else:
            final_grade = 'D'
            feedback = "📚 需改进！建议系统学习销售话术技巧。" 
         
        # 生成各轮得分明细 
        stages = ['开场白', '探询需求', '产品介绍', '产品介绍', '处理异议', '处理异议', '促成成交', '结束']
        lines = []
        for i, s in enumerate(session['scores']):
            bar = '█' * (s['score'] // 2) + '░' * (5 - s['score'] // 2)
            lines.append(f"  {i+1}. {stages[i]}: {bar} {s['score']}/10 ({s['grade']})") 
         
        # 收集亮点和改进点 
        all_strengths = []
        all_weaknesses = []
        for s in session['scores']:
            all_strengths.extend(s['strengths'])
            all_weaknesses.extend(s['weaknesses']) 

        strengths_text = '\n'.join([f"  ✅ {s}" for s in set(all_strengths)[:3]]) if all_strengths else "  继续保持！"
        weaknesses_text = '\n'.join([f"  💡 {w}" for w in set(all_weaknesses)[:3]]) if all_weaknesses else "  表现不错！" 

        del user_sessions[user_id] 

        return f"""🎉 对练完成！ 
 
📊 综合评分：{avg:.1f}/10 (等级{final_grade}) 
💬 总体评价：{feedback} 
 
📋 各轮得分： 
{chr(10).join(lines)} 
 
🌟 亮点： 
{strengths_text} 
 
📝 待改进： 
{weaknesses_text} 
 
发送【开始练习】重新开始""" 
     
    # 生成AI医生回复 
    doctor_response = generate_doctor_response(text, role, step, session['history']) 
     
    # 更新历史 
    session['history'][-1]['doctor'] = doctor_response 
     
    # 增加轮数 
    session['step'] = step + 1 

    stages = ['开场白', '探询需求', '产品介绍', '产品介绍', '处理异议', '处理异议', '促成成交', '结束'] 

    return f"""👨‍⚕️ 医生说："{doctor_response}" 
 
📊 上轮评分：{evaluation['score']}/10 (等级{evaluation['grade']}) 
💬 反馈：{evaluation['feedback']} 
 
🎬 第{step + 1}轮：{stages[step]} 
💬 请回复...""" 
 
@app.route('/') 
def index():
    return jsonify({'status': 'ok', 'version': 'ai-smart-v1.0', 'features': ['AI智能对话', 'LLM生成回复', '实时评估', '完整8轮']}) 
 
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

        if header.get('event_type') == 'im.message.receive_v1':
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

            if text and user_id:
                reply = handle_msg(text, user_id, msg_id)
                send_msg(user_id, msg_id, reply) 

        return jsonify({'status': 'ok'}) 
    except Exception as e:
        import traceback
        print(f"Error: {e}")
        print(traceback.format_exc())
        return jsonify({'status': 'error', 'message': str(e)}), 500 

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
