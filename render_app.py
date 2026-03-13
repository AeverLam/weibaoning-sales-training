#!/usr/bin/env python3
#### -*- coding: utf-8 -*-
"""
维宝宁销售话术对练 - 飞书机器人
"""

import json
import os
import sys
import re
from datetime import datetime
from flask import Flask, request, jsonify

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from feishu_api import get_feishu_api

app = Flask(__name__)

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
• 帮助 - 显示本菜单"""
        
        else:
            return f"收到您的消息：{message_text}\n\n发送【开始练习】开始销售话术对练！"

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

def remove_mentions(text):
    """移除消息中的@mention"""
    text = re.sub(r'@_user_\w+\s*', '', text)
    text = re.sub(r'@\S+\s*', '', text)
