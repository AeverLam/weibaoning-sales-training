#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
维宝宁销售话术对练 - 极简稳定版
确保：不重复、8轮、有评分
"""

import json
import os
import threading
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

FEISHU_APP_ID = os.environ.get('FEISHU_APP_ID', 'cli_a938ac2a24391bcb')
FEISHU_APP_SECRET = os.environ.get('FEISHU_APP_SECRET', '')

# 简单内存存储（Render重启会丢，但避免文件并发问题）
users = {}

# 医生角色
ROLES = {
    '1': ('主任级专家', '⭐⭐⭐⭐⭐', '学术权威、严谨'),
    '2': ('科室主任', '⭐⭐⭐⭐', '务实、时间紧张'),
    '3': ('主治医师', '⭐⭐⭐', '经验丰富、实用导向'),
    '4': ('住院医师', '⭐⭐', '学习热情高'),
    '5': ('带组专家', '⭐⭐⭐⭐⭐', '影响力大、决策权高')
}

# 8轮对话模板
DIALOGUE = [
    ("你好，有什么事吗？我一会儿还有台手术。", "开场白", 6),
    ("我们科室确实有不少内异症患者，现在主要用亮丙瑞林。你说的这个维宝宁有什么特别的？", "探询需求", 7),
    ("E2去势率97.45%？这个数据不错，有III期临床数据支持吗？", "产品介绍", 8),
    ("网状Meta分析94项RCT？妊娠率87.3%确实比竞品高。", "产品介绍", 9),
    ("价格怎么样？1000元/支的支付标准，患者自付多少？", "处理异议", 7),
    ("不良反应发生率确实很低，长期安全性数据怎么样？", "处理异议", 8),
    ("听起来不错，要不你先放几份样品，我给几个患者试试。", "促成成交", 9),
    ("今天的交流很有收获，维宝宁的数据确实令人信服。", "结束", 10)
]

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
            if not token:
                return
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            if msg_id:
                url = f"https://open.feishu.cn/open-apis/im/v1/messages/{msg_id}/reply"
                data = {"content": json.dumps({"text": text})}
            else:
                url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"
                data = {"receive_id": open_id, "msg_type": "text", "content": json.dumps({"text": text})}
            requests.post(url, headers=headers, json=data, timeout=10)
        except Exception as e:
            print(f"[send error] {e}")
    threading.Thread(target=do, daemon=True).start()

def handle_msg(text, user_id):
    text = text.strip()
    
    # 开始
    if text in ['开始练习', '开始对练', 'start', '开始']:
        users[user_id] = {'step': 0, 'role': None, 'scores': []}
        return "👋 欢迎开始维宝宁销售话术对练！\n\n请选择医生角色（回复数字）：\n1. 主任级专家 ⭐⭐⭐⭐⭐\n2. 科室主任 ⭐⭐⭐⭐\n3. 主治医师 ⭐⭐⭐\n4. 住院医师 ⭐⭐\n5. 带组专家 ⭐⭐⭐⭐⭐"
    
    # 帮助
    if text in ['帮助', 'help', '?']:
        return "🤖 指令：开始练习 | 结束 | 状态 | 帮助"
    
    # 结束
    if text in ['结束', 'stop', 'quit']:
        if user_id in users:
            del users[user_id]
        return "对练已结束。发送【开始练习】重新开始"
    
    # 状态
    if text in ['状态', 'status']:
        u = users.get(user_id)
        if not u:
            return "当前没有对练"
        return f"🎭 角色：{u['role'] or '未选择'}\n🔄 轮次：第{u['step']}轮/共8轮\n📈 得分：{sum(u['scores'])/len(u['scores']) if u['scores'] else 0:.1f}"
    
    # 获取用户状态
    u = users.get(user_id)
    if not u:
        return "发送【开始练习】开始"
    
    # 选择角色
    if u['step'] == 0:
        if text in ROLES:
            role_name, stars, desc = ROLES[text]
            u['role'] = role_name
            u['step'] = 1
            doctor_text, stage, score = DIALOGUE[0]
            u['scores'].append(score)
            return f"✅ 已选择：{role_name} {stars}\n\n🎬 第1轮：开场白\n\n👨‍⚕️ 医生说：{doctor_text}\n\n💬 请回复你的开场白..."
        return "请选择 1-5"
    
    # 对话中
    step = u['step']
    if step >= 8:
        # 结束报告
        avg = sum(u['scores']) / len(u['scores'])
        lines = []
        for i, s in enumerate(u['scores']):
            name = ['开场白','探询需求','产品介绍','产品介绍','处理异议','处理异议','促成成交','结束'][i]
            lines.append(f"  {i+1}. {name}: {'█'*(s//2)}{'░'*(5-s//2)} {s}/10")
        del users[user_id]
        return f"🎉 对练完成！\n\n📊 综合评分：{avg:.1f}/10\n\n📋 各轮得分：\n{chr(10).join(lines)}\n\n发送【开始练习】重新开始"
    
    # 计算用户得分（简单关键词匹配）
    user_score = 6
    keywords = ['E2','去势率','97%','微球','辅料','副作用','疼痛','临床','Meta','妊娠率','复发率','价格','医保','安全性']
    matches = sum(1 for k in keywords if k in text)
    user_score = min(6 + matches, 10)
    u['scores'].append(user_score)
    
    # 进入下一轮
    u['step'] = step + 1
    doctor_text, stage, doctor_score = DIALOGUE[step]
    
    return f"👨‍⚕️ 医生说：{doctor_text}\n\n📊 上轮评分：{user_score}/10\n\n🎬 第{step+1}轮：{stage}\n💬 请回复..."

@app.route('/')
def index():
    return jsonify({'status': 'ok', 'version': 'simple-v1'})

@app.route('/webhook/feishu', methods=['POST', 'GET'])
def webhook():
    try:
        if request.method == 'GET':
            return jsonify({'status': 'ok'})
        
        data = request.get_json() or {}
        
        # URL验证
        if 'challenge' in data:
            return jsonify({'challenge': data['challenge']})
        
        # 处理消息
        header = data.get('header', {})
        event = data.get('event', {})
        
        if header.get('event_type') == 'im.message.receive_v1':
            message = event.get('message', {})
            sender = event.get('sender', {})
            
            if message.get('message_type') == 'text':
                try:
                    text = json.loads(message.get('content', '{}')).get('text', '').strip()
                except:
                    text = message.get('content', '').strip()
                
                user_id = sender.get('sender_id', {}).get('open_id', '')
                msg_id = message.get('message_id', '')
                
                print(f"[recv] {user_id}: {text[:30]}")
                
                reply = handle_msg(text, user_id)
                send_msg(user_id, msg_id, reply)
        
        return jsonify({'status': 'ok'})
    except Exception as e:
        print(f"[error] {e}")
        return jsonify({'status': 'error'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
