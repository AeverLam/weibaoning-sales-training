#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
维宝宁销售话术对练 - AI智能版飞书机器人 (简化版)
"""
import json
import os
import threading
import requests
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

FEISHU_APP_ID = os.environ.get('FEISHU_APP_ID', 'cli_a938ac2a24391bcb')
FEISHU_APP_SECRET = os.environ.get('FEISHU_APP_SECRET', '')

# 内存存储
users = {}

ROLES = {
    '1': ('主任级专家', '学术型', '⭐⭐⭐⭐⭐'),
    '2': ('科室主任', '管理型', '⭐⭐⭐⭐'),
    '3': ('主治医师', '实用型', '⭐⭐⭐'),
    '4': ('住院医师', '学习型', '⭐⭐'),
    '5': ('带组专家', '影响力型', '⭐⭐⭐⭐⭐')
}

# 医生回复模板（基于角色类型）
DOCTOR_RESPONSES = {
    '科室主任': [
        "你好，有什么事吗？我一会儿还有台手术。",
        "我们科室确实有不少内异症患者，现在主要用亮丙瑞林。你说的这个维宝宁有什么特别的？",
        "E2去势率97.45%？这个数据不错，有III期临床数据支持吗？",
        "网状Meta分析94项RCT？妊娠率87.3%确实比竞品高。",
        "价格怎么样？1000元/支的支付标准，患者自付多少？",
        "不良反应发生率确实很低，长期安全性数据怎么样？",
        "听起来不错，要不你先放几份样品，我给几个患者试试。",
        "今天的交流很有收获，维宝宁的数据确实令人信服。"
    ],
    '主任级专家': [
        "你好，我时间有限，请长话短说。",
        "内异症确实是我们关注的重点，你有什么新的循证医学证据？",
        "97.45%的E2去势率？样本量多大？统计学意义如何？",
        "网状Meta分析？发表在什么期刊上？影响因子多少？",
        "价格不是主要问题，关键是疗效和安全性要有充分证据。",
        "长期随访数据怎么样？有5年以上的安全性数据吗？",
        "如果数据确实可靠，可以在我们科室试点使用。",
        "你的专业水平不错，期待看到更多临床数据。"
    ],
    '主治医师': [
        "你好，有什么事？",
        "我们确实有不少内异症患者，现在用的药效果一般。",
        "维宝宁？没听说过，效果怎么样？",
        "有临床数据支持吗？其他医院用得怎么样？",
        "价格贵不贵？患者能接受吗？",
        "副作用大吗？患者反馈如何？",
        "可以先试试，如果效果好我会继续用的。",
        "今天了解了不少，谢谢你的介绍。"
    ],
    '住院医师': [
        "你好，请问有什么事？",
        "内异症？我们科室确实有不少这类患者。",
        "维宝宁是什么药？主要适应症是什么？",
        "用法用量是怎样的？有什么禁忌症？",
        "价格怎么样？医保能报销吗？",
        "不良反应有哪些？需要特别注意什么？",
        "有学习资料吗？我想多了解一下。",
        "谢谢你的介绍，我会向主任汇报的。"
    ],
    '带组专家': [
        "你好，请简单介绍一下。",
        "内异症是我们重点关注的领域，有什么新的进展？",
        "维宝宁的学术价值在哪里？对学科发展有什么帮助？",
        "有高质量的临床研究支持吗？适合在学术会议上分享吗？",
        "价格因素需要考虑，但更重要的是学术影响力。",
        "安全性数据怎么样？适合带教使用吗？",
        "如果确实有价值，我可以考虑在学术会议上介绍。",
        "你的介绍很专业，期待进一步合作。"
    ]
}

STAGES = ['开场白', '探询需求', '产品介绍', '产品介绍', '处理异议', '处理异议', '促成成交', '结束']

def get_token():
    try:
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        resp = requests.post(url, json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}, timeout=10)
        return resp.json().get("tenant_access_token")
    except:
        return None

def send_msg(open_id, msg_id, text):
    def do():
        try:
            token = get_token()
            if not token: return
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            if msg_id:
                url = f"https://open.feishu.cn/open-apis/im/v1/messages/{msg_id}/reply"
                data = {"msg_type": "text", "content": json.dumps({"text": text})}
            else:
                url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"
                data = {"receive_id": open_id, "msg_type": "text", "content": json.dumps({"text": text})}
            requests.post(url, headers=headers, json=data, timeout=10)
        except: pass
    threading.Thread(target=do, daemon=True).start()

def evaluate_response(text, stage_name):
    """评估用户回答"""
    score = 6
    keywords = ['E2','去势率','97%','微球','亮丙瑞林','副作用','疼痛','临床','Meta','妊娠率','复发率','价格','医保','安全性','样品','试用','优势','数据','效果']
    matches = sum(1 for k in keywords if k in text)
    score = min(6 + matches, 10)
    
    if score >= 9:
        feedback = "🌟 表现优秀！话术专业、逻辑清晰。"
        grade = "A"
    elif score >= 7:
        feedback = "👍 表现良好，掌握了基本技巧。"
        grade = "B"
    elif score >= 5:
        feedback = "💡 表现一般，还有提升空间。"
        grade = "C"
    else:
        feedback = "📝 建议多练习产品知识和话术技巧。"
        grade = "D"
    
    return score, grade, feedback

def get_final_feedback(scores):
    avg = sum(scores) / len(scores)
    if avg >= 9:
        return "🏆 优秀！你的销售话术非常专业，能够灵活应对各种场景。"
    elif avg >= 7:
        return "🥈 良好！你掌握了基本的销售话术技巧，但在某些环节还有提升空间。"
    elif avg >= 5:
        return "🥉 及格！你对产品有一定了解，但话术需要更加熟练。"
    else:
        return "📚 需改进！建议系统学习销售话术技巧，从基础开始逐步提升。"

def handle_msg(text, user_id):
    text = text.strip()
    
    if text in ['开始练习', 'start', '开始']:
        users[user_id] = {'step': 0, 'role': None, 'scores': [], 'role_name': None}
        return "👋 欢迎开始维宝宁销售话术对练（AI智能版）！\n\n请选择医生角色（回复数字）：\n1️⃣ 主任级专家 ⭐⭐⭐⭐⭐\n2️⃣ 科室主任 ⭐⭐⭐⭐\n3️⃣ 主治医师 ⭐⭐⭐\n4️⃣ 住院医师 ⭐⭐\n5️⃣ 带组专家 ⭐⭐⭐⭐⭐"
    
    if text in ['结束', 'stop']:
        if user_id in users: del users[user_id]
        return "对练已结束。发送【开始练习】重新开始"
    
    u = users.get(user_id)
    if not u or u.get('step', -1) < 0:
        return "发送【开始练习】开始"
    
    if u['step'] == 0:
        if text in ROLES:
            role_name, role_type, stars = ROLES[text]
            u['role'] = text
            u['role_name'] = role_name
            u['step'] = 1
            u['scores'] = []
            
            # 获取医生开场白
            doctor_text = DOCTOR_RESPONSES.get(role_name, DOCTOR_RESPONSES['科室主任'])[0]
            
            return f"✅ 已选择：{role_name} {stars}\n类型：{role_type}\n\n🎬 第1轮：开场白\n\n👨‍⚕️ 医生说：\"{doctor_text}\"\n\n💬 请回复你的开场白..."
        return "请选择 1-5"
    
    step = u['step']
    role_name = u.get('role_name', '科室主任')
    
    # 计算得分
    current_stage = STAGES[step - 1] if step > 0 else STAGES[0]
    score, grade, feedback = evaluate_response(text, current_stage)
    u['scores'].append(score)
    
    # 完成8轮
    if step >= 8:
        avg = sum(u['scores']) / len(u['scores'])
        final_feedback = get_final_feedback(u['scores'])
        
        lines = []
        for i, s in enumerate(u['scores']):
            name = STAGES[i]
            bar = '█'*(s//2) + '░'*(5-s//2)
            lines.append(f"  {i+1}. {name}: {bar} {s}/10")
        
        result = f"🎉 对练完成！\n\n📊 综合评分：{avg:.1f}/10\n\n📋 各轮得分：\n" + "\n".join(lines) + f"\n\n💬 本轮反馈：\n{feedback}\n\n📝 总体评价：\n{final_feedback}\n\n发送【开始练习】重新开始"
        
        del users[user_id]
        return result
    
    # 进入下一轮
    u['step'] = step + 1
    
    # 获取医生回复
    doctor_responses = DOCTOR_RESPONSES.get(role_name, DOCTOR_RESPONSES['科室主任'])
    doctor_text = doctor_responses[min(step, len(doctor_responses) - 1)]
    next_stage = STAGES[step]
    
    return f"👨‍⚕️ 医生说：\"{doctor_text}\"\n\n📊 上轮评分：{score}/10 (等级{grade})\n💬 反馈：{feedback}\n\n🎬 第{step+1}轮：{next_stage}\n请回复..."

@app.route('/')
def index():
    return jsonify({'status': 'ok', 'version': 'ai-simple-v1.0'})

@app.route('/webhook/feishu', methods=['POST', 'GET'])
def webhook():
    try:
        if request.method == 'GET':
            return jsonify({'status': 'ok'})
        
        data = request.get_json() or {}
        
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
                
                text = text.replace('@_user_1', '').replace('@维宝宁销售训练助手', '').strip()
                
                user_id = sender.get('sender_id', {}).get('open_id', '')
                msg_id = message.get('message_id', '')
                
                if text and user_id:
                    reply = handle_msg(text, user_id)
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