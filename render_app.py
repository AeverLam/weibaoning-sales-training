#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
维宝宁销售话术对练 - Render Web 服务
飞书机器人 Webhook 处理器
"""

import json
import os
import hashlib
import base64
from datetime import datetime
from flask import Flask, request, jsonify
import sys
import threading

# 添加脚本目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入业务逻辑
from feishu_bot import FeishuMessageHandler
from feishu_api import get_feishu_api

app = Flask(__name__)

# 环境变量
FEISHU_APP_ID = os.environ.get('FEISHU_APP_ID', '')
FEISHU_APP_SECRET = os.environ.get('FEISHU_APP_SECRET', '')
FEISHU_ENCRYPT_KEY = os.environ.get('FEISHU_ENCRYPT_KEY', '')
FEISHU_VERIFICATION_TOKEN = os.environ.get('FEISHU_VERIFICATION_TOKEN', '')

# 消息处理器
handler = FeishuMessageHandler()


def send_reply_async(open_id: str, message_id: str, text: str):
    """异步发送消息回复"""
    def send():
        try:
            api = get_feishu_api()
            if api:
                # 优先使用消息回复功能
                if message_id:
                    result = api.reply_message(message_id, text)
                    print(f"[回复消息] message_id={message_id}, result={result}")
                else:
                    result = api.send_text_message(open_id, text)
                    print(f"[发送消息] open_id={open_id}, result={result}")
            else:
                print("[错误] 飞书API未初始化，无法发送消息")
        except Exception as e:
            print(f"[错误] 发送消息失败: {e}")
            import traceback
            traceback.print_exc()
    
    # 启动后台线程发送消息
    thread = threading.Thread(target=send)
    thread.daemon = True
    thread.start()


@app.route('/')
def index():
    """首页 - 健康检查"""
    return jsonify({
        'status': 'ok',
        'service': '维宝宁销售话术对练',
        'version': '1.0.0',
        'timestamp': datetime.now().isoformat(),
        'app_id': FEISHU_APP_ID[:10] + '...' if FEISHU_APP_ID else '未设置'
    })


@app.route('/health')
def health():
    """健康检查端点"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })


@app.route('/webhook/feishu', methods=['POST', 'GET'])
def webhook_feishu():
    """
    飞书机器人 Webhook 入口
    处理：
    1. URL 验证（challenge）
    2. 消息接收
    3. 消息回复（异步）
    """
    try:
        # GET 请求返回基本信息
        if request.method == 'GET':
            return jsonify({
                'status': 'ok',
                'message': '飞书 webhook 服务正常运行'
            })
        
        # POST 请求处理飞书消息
        body = request.get_data(as_text=True)
        data = request.get_json() or {}
        
        print(f"[飞书 Webhook] 收到消息: {json.dumps(data, ensure_ascii=False)[:500]}")
        
        # 1. 处理 URL 验证（challenge）
        challenge = data.get('challenge')
        if challenge:
            print(f"[验证] 收到 challenge: {challenge}")
            return jsonify({'challenge': challenge})
        
        # 2. 处理加密消息
        encrypt = data.get('encrypt')
        if encrypt:
            # 如果有加密，这里需要解密
            print(f"[加密消息] 收到加密消息，暂不解密处理")
            return jsonify({'status': 'ok'})
        
        # 3. 处理事件回调
        header = data.get('header', {})
        event = data.get('event', {})
        
        event_type = header.get('event_type', '')
        
        # 处理消息事件
        if event_type == 'im.message.receive_v1':
            message = event.get('message', {})
            sender = event.get('sender', {})
            
            # 提取消息信息
            message_type = message.get('message_type', '')
            content = message.get('content', '{}')
            message_id = message.get('message_id', '')
            
            try:
                content_data = json.loads(content)
            except:
                content_data = {'text': content}
            
            # 获取文本消息
            if message_type == 'text':
                message_text = content_data.get('text', '').strip()
            else:
                message_text = '[非文本消息]'
            
            # 获取用户信息
            sender_id = sender.get('sender_id', {}).get('open_id', '')
            
            print(f"[消息] 用户({sender_id}): {message_text}")
            
            # 处理消息
            reply_text = handler.handle_message(message_text, sender_id, "用户")
            
            # 异步发送回复
            send_reply_async(sender_id, message_id, reply_text)
            
            # 立即返回成功响应
            return jsonify({'status': 'ok'})
        
        # 处理应用启动事件
        elif event_type == 'application.bot.menu_v1':
            print(f"[事件] 用户点击菜单")
            return jsonify({'status': 'ok'})
        
        # 其他事件
        else:
            print(f"[事件] 收到其他类型事件: {event_type}")
            return jsonify({'status': 'ok'})
        
    except Exception as e:
        print(f"[错误] Webhook 处理异常: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/webhook/feishu/test', methods=['POST'])
def webhook_feishu_test():
    """测试端点 - 模拟飞书消息"""
    data = request.get_json() or {}
    
    message_text = data.get('text', '开始练习')
    user_id = data.get('user_id', 'test_user_001')
    user_name = data.get('user_name', '测试用户')
    
    reply = handler.handle_message(message_text, user_id, user_name)
    
    return jsonify({
        'user_message': message_text,
        'bot_reply': reply
    })


@app.route('/api/send_message', methods=['POST'])
def api_send_message():
    """API端点 - 发送消息"""
    data = request.get_json() or {}
    
    open_id = data.get('open_id', '')
    text = data.get('text', '')
    
    if not open_id or not text:
        return jsonify({'error': 'Missing open_id or text'}), 400
    
    api = get_feishu_api()
    if not api:
        return jsonify({'error': 'Feishu API not configured'}), 500
    
    result = api.send_text_message(open_id, text)
    return jsonify(result)


if __name__ == '__main__':
    # 本地开发模式
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
