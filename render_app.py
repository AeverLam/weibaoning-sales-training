#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
维宝宁销售话术对练 - 简化版飞书机器人
不依赖外部脚本，独立运行
"""

import json
import os
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

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


@app.route('/')
def index():
    return jsonify({
        'status': 'ok',
        'service': '维宝宁销售话术对练',
        'version': '1.0.0',
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
        
        # URL 验证
        challenge = data.get('challenge')
        if challenge:
            return jsonify({'challenge': challenge})
        
        # 处理消息
        event = data.get('event', {})
        message = event.get('message', {})
        sender = event.get('sender', {})
        
        message_type = message.get('message_type', '')
        content = message.get('content', '{}')
        
        try:
            content_data = json.loads(content)
        except:
            content_data = {'text': content}
        
        if message_type == 'text':
            message_text = content_data.get('text', '').strip()
        else:
            message_text = '[非文本消息]'
        
        sender_id = sender.get('sender_id', {}).get('open_id', '')
        
        # 处理消息
        reply_text = handler.handle_message(message_text, sender_id, "用户")
        
        return jsonify({'status': 'ok'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
