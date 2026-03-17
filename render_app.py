#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, os, threading, requests
from flask import Flask, request, jsonify
app = Flask(__name__)
FEISHU_APP_ID = os.environ.get('FEISHU_APP_ID', 'cli_a938ac2a24391bcb')
FEISHU_APP_SECRET = os.environ.get('FEISHU_APP_SECRET', '')
users = {}
ROLES = {
    '1': ('主任级专家', '⭐⭐⭐⭐⭐'),
    '2': ('科室主任', '⭐⭐⭐⭐'),
    '3': ('主治医师', '⭐⭐⭐'),
    '4': ('住院医师', '⭐⭐'),
    '5': ('带组专家', '⭐⭐⭐⭐⭐')
}
DIALOGUE = [
    "你好，有什么事吗？我一会儿还有台手术。",
    "我们科室确实有不少内异症患者，现在主要用亮丙瑞林。你说的这个维宝宁有什么特别的？",
    "E2去势率97.45%？这个数据不错，有III期临床数据支持吗？",
    "网状Meta分析94项RCT？妊娠率87.3%确实比竞品高。",
    "价格怎么样？1000元/支的支付标准，患者自付多少？",
    "不良反应发生率确实很低，长期安全性数据怎么样？",
    "听起来不错，要不你先放几份样品，我给几个患者试试。",
    "今天的交流很有收获，维宝宁的数据确实令人信服。"
]
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
# 新增：根据得分和阶段给出反馈
def get_feedback(score, stage_name):
    if score >= 9:
        return "🌟 表现优秀！话术专业、逻辑清晰。"
    elif score >= 7:
        return "👍 表现良好，掌握了基本技巧。"
    elif score >= 5:
        return "💡 表现一般，还有提升空间。"
    else:
        if '开场白' in stage_name:
            return "📝 建议：开场白可以更简洁有力，快速建立信任。"
        elif '产品介绍' in stage_name:
            return "📝 建议：注意使用FAB法则（特性-优势-利益）。"
        elif '异议' in stage_name:
            return "📝 建议：先认同再回应，使用APRC法则。"
        else:
            return "📝 建议：多练习产品知识和话术技巧。"
# 新增：根据总分给出最终评价
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
        users[user_id] = {'step': 0, 'role': None, 'scores': []}
        return "👋 欢迎开始维宝宁销售话术对练！\n\n请选择医生角色（回复数字）：\n1. 主任级专家 ⭐⭐⭐⭐⭐\n2. 科室主任 ⭐⭐⭐⭐\n3. 主治医师 ⭐⭐⭐\n4. 住院医师 ⭐⭐\n5. 带组专家 ⭐⭐⭐⭐⭐"
    
    if text in ['结束', 'stop']:
        if user_id in users: del users[user_id]
        return "对练已结束。发送【开始练习】重新开始"
    
    u = users.get(user_id)
    if not u:
        return "发送【开始练习】开始"
    
    if u['step'] == 0:
        if text in ROLES:
            role_name, stars = ROLES[text]
            u['role'] = role_name
            u['step'] = 1
            doctor_text = DIALOGUE[0]
            u['scores'].append(6)
            return f"✅ 已选择：{role_name} {stars}\n\n🎬 第1轮：开场白\n\n👨‍⚕️ 医生说：{doctor_text}\n\n💬 请回复你的开场白..."
        return "请选择 1-5"
    
    step = u['step']
    
    # 计算用户得分
    user_score = 6
    keywords = ['E2','去势率','97%','微球','辅料','副作用','疼痛','临床','Meta','妊娠率','复发率','价格','医保','安全性','样品','试用','优势','数据','效果']
    matches = sum(1 for k in keywords if k in text)
    user_score = min(6 + matches, 10)
    u['scores'].append(user_score)
    
    # 获取当前阶段的反馈（新增）
    current_stage = STAGES[step - 1] if step > 0 else STAGES[0]
    feedback = get_feedback(user_score, current_stage)
    
    # 检查是否完成8轮（修改：第8轮用户回复后结束并显示总结）
    if step >= 8:
        avg = sum(u['scores']) / len(u['scores'])
        final_feedback = get_final_feedback(u['scores'])
        lines = []
        for i, s in enumerate(u['scores']):
            name = STAGES[i]
            bar = '█'*(s//2) + '░'*(5-s//2)
            lines.append(f"  {i+1}. {name}: {bar} {s}/10")
        del users[user_id]
        return f"🎉 对练完成！\n\n📊 综合评分：{avg:.1f}/10\n\n📋 各轮得分：\n" + "\n".join(lines) + f"\n\n💬 本轮反馈：\n{feedback}\n\n📝 总体评价：\n{final_feedback}\n\n发送【开始练习】重新开始"
    
    # 进入下一轮（修改：增加反馈）
    u['step'] = step + 1
    doctor_text = DIALOGUE[step]
    next_stage = STAGES[step]
    
    return f"👨‍⚕️ 医生说：{doctor_text}\n\n📊 上轮评分：{user_score}/10\n💬 反馈：{feedback}\n\n🎬 第{step+1}轮：{next_stage}\n请回复..."
@app.route('/')
def index():
    return jsonify({'status': 'ok', 'version': 'final-v2'})
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
                
                # 去掉@机器人的部分
                text = text.replace('@_user_1', '').replace('@维宝宁销售训练助手', '').strip()
                
                user_id = sender.get('sender_id', {}).get('open_id', '')
                msg_id = message.get('message_id', '')
                
                if text and user_id:
                    reply = handle_msg(text, user_id)
                    send_msg(user_id, msg_id, reply)
        
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'status': 'error'}), 500
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
