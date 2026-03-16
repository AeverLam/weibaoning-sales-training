#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
维宝宁销售话术对练 - 飞书机器人
支持异步消息回复
"""

import json
import os
import threading
import requests
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

# 环境变量
FEISHU_APP_ID = os.environ.get('FEISHU_APP_ID', 'cli_a938ac2a24391bcb')
FEISHU_APP_SECRET = os.environ.get('FEISHU_APP_SECRET', '')

# 简化的消息处理器
class FeishuMessageHandler:
    def handle_message(self, message_text, user_id, user_name=""):
        message_text = message_text.strip()
        
        if message_text in ['开始练习', '开始对练', 'start']:
            return """👋 您好！欢迎开始维宝宁销售话术对练。

请回复数字选择医生角色：
1. 主任级专家（难度⭐⭐⭐⭐⭐）
2. 科室主任（难度⭐⭐⭐⭐）
3. 主治医师（难度⭐⭐⭐）
4. 住院医师（难度⭐⭐）
5. 带组专家（难度⭐⭐⭐⭐）

💡 建议从难度3星的【主治医师】开始练习！"""
        
        elif message_text in ['帮助', 'help', '菜单']:
            return """🤖 维宝宁销售话术对练助手

📋 常用指令：
• 开始练习 - 开始新的销售话术对练
• 帮助 - 显示本菜单

💡 练习流程：
1. 发送"开始练习"
2. 选择医生角色（1-5）
3. 根据医生提问回复销售话术
4. 系统自动评估并给出反馈
5. 发送"结束"查看学习报告"""
        
        else:
            return f"收到您的消息：{message_text}\n\n发送【开始练习】开始销售话术对练，或发送【帮助】查看指令列表。"

handler = FeishuMessageHandler()

def get_tenant_access_token():
    """获取飞书 tenant access token"""
    try:
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        headers = {"Content-Type": "application/json"}
        data = {
            "app_id": FEISHU_APP_ID,
            "app_secret": FEISHU_APP_SECRET
        }
        resp = requests.post(url, headers=headers, json=data, timeout=10)
        result = resp.json()
        return result.get("tenant_access_token")
    except Exception as e:
        print(f"[错误] 获取token失败: {e}")
        return None

def send_message_async(open_id, message_id, text):
    """异步发送消息回复"""
    def send():
        try:
            print(f"[调试] 开始发送消息，open_id={open_id[:10]}...")            
            token = get_tenant_access_token()
            print(f"[调试] 获取token成功: {token[:20]}...")           
            if not token:
                print("[错误] 无法获取token")
                return
            
            url = "https://open.feishu.cn/open-apis/im/v1/messages"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            # 如果有 message_id，则回复该消息
            if message_id:
                url = f"{url}/{message_id}/reply"
                data = {
                    "content": json.dumps({"text": text})
                }
            else:
                # 否则发送新消息
                params = {"receive_id_type": "open_id"}
                data = {
                    "receive_id": open_id,
                    "msg_type": "text",
                    "content": json.dumps({"text": text})
                }
                url = f"{url}?{requests.compat.urlencode(params)}"
            
            print(f"[调试] 发送请求，url={url[:50]}...")            
            resp = requests.post(url, headers=headers, json=data, timeout=10)
            print(f"[发送消息] status={resp.status_code}, response={resp.text[:200]}")
            if resp.status_code != 200:
                print(f"[错误] 发送失败: {resp.text}") 
            
        except Exception as e:
            print(f"[错误] 发送消息失败: {e}")
    
    thread = threading.Thread(target=send)
    thread.daemon = True
    thread.start()
    
@app.route('/')
def index():
    return jsonify({
        'status': 'ok',
        'service': '维宝宁销售话术对练',
        'version': '1.0.1',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})

@app.route('/webhook/feishu', methods=['POST', 'GET'])
def webhook_feishu():
    try:
        if request.method == 'GET':
            return jsonify({'status': 'ok', 'message': '飞书 webhook 服务正常运行'})
        
        data = request.get_json() or {}
        print(f"[收到请求] {json.dumps(data, ensure_ascii=False)[:500]}")
        
        # URL 验证
        challenge = data.get('challenge')
        if challenge:
            return jsonify({'challenge': challenge})
        
        # 处理消息
        header = data.get('header', {})
        event = data.get('event', {})
        
        event_type = header.get('event_type', '')
        
        if event_type == 'im.message.receive_v1':
            message = event.get('message', {})
            sender = event.get('sender', {})
            
            message_type = message.get('message_type', '')
            content = message.get('content', '{}')
            message_id = message.get('message_id', '')
            
            try:
                content_data = json.loads(content)
            except:
                content_data = {'text': content}
            
            if message_type == 'text':
                message_text = content_data.get('text', '').strip()
            else:
                message_text = '[非文本消息]'
            
            sender_id = sender.get('sender_id', {}).get('open_id', '')
            
            print(f"[消息] 用户({sender_id}): {message_text}")
            
            # 处理消息
            reply_text = handler.handle_message(message_text, sender_id, "用户")
            
            # 异步发送回复
            send_message_async(sender_id, message_id, reply_text)
            
            return jsonify({'status': 'ok'})
        
        return jsonify({'status': 'ok'})
        
    except Exception as e:
        print(f"[错误] Webhook处理异常: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
