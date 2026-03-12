#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
维宝宁销售话术对练 - 微信公众号消息处理器
部署在服务器上接收微信消息并处理对练请求
与飞书版共用核心业务逻辑
"""

import json
import sys
import os
import hashlib
import time
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional

# 添加脚本目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 复用飞书版的业务逻辑
from feishu_bot import FeishuMessageHandler

class WechatMessageHandler:
    """微信公众号消息处理器"""
    
    def __init__(self, token: str, app_id: str, app_secret: str):
        self.token = token
        self.app_id = app_id
        self.app_secret = app_secret
        self.feishu_handler = FeishuMessageHandler()  # 复用飞书版业务逻辑
        
    def verify_signature(self, signature: str, timestamp: str, nonce: str) -> bool:
        """验证微信服务器签名"""
        tmp_list = [self.token, timestamp, nonce]
        tmp_list.sort()
        tmp_str = ''.join(tmp_list)
        hashcode = hashlib.sha1(tmp_str.encode()).hexdigest()
        return hashcode == signature
    
    def parse_xml_message(self, xml_data: str) -> Dict:
        """解析微信XML消息"""
        root = ET.fromstring(xml_data)
        message = {}
        
        for child in root:
            message[child.tag] = child.text
        
        return message
    
    def generate_xml_reply(self, to_user: str, from_user: str, content: str) -> str:
        """生成XML回复消息"""
        timestamp = int(time.time())
        
        xml_template = f"""<xml>
<ToUserName><![CDATA[{to_user}]]></ToUserName>
<FromUserName><![CDATA[{from_user}]]></FromUserName>
<CreateTime>{timestamp}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[{content}]]></Content>
</xml>"""
        
        return xml_template
    
    def handle_message(self, xml_data: str) -> str:
        """处理微信消息并返回回复"""
        # 解析消息
        message = self.parse_xml_message(xml_data)
        
        msg_type = message.get('MsgType', '')
        user_id = message.get('FromUserName', '')
        to_user = message.get('ToUserName', '')
        
        # 只处理文本消息
        if msg_type == 'text':
            content = message.get('Content', '')
            
            # 复用飞书版的业务逻辑处理消息
            reply_content = self.feishu_handler.handle_message(content, user_id, "微信用户")
            
            # 生成XML回复
            return self.generate_xml_reply(user_id, to_user, reply_content)
        
        # 其他类型消息返回空
        return "success"
    
    def handle_event(self, xml_data: str) -> str:
        """处理微信事件（关注、取消关注等）"""
        message = self.parse_xml_message(xml_data)
        event = message.get('Event', '')
        user_id = message.get('FromUserName', '')
        to_user = message.get('ToUserName', '')
        
        if event == 'subscribe':
            # 用户关注时发送欢迎消息
            welcome_msg = """🎉 欢迎使用维宝宁销售话术对练助手！

我是您的AI销售教练，帮助您提升维宝宁产品销售话术。

📚 功能介绍：
• 开始练习 - 与AI医生进行销售对练
• 5种医生角色 - 从住院医师到主任级专家
• 实时评估 - 获得专业反馈和改进建议
• 学习报告 - 追踪学习进度

💡 发送"开始练习"立即开始！

或发送"帮助"查看完整指令。"""
            
            return self.generate_xml_reply(user_id, to_user, welcome_msg)
        
        return "success"


# Flask Web服务入口
from flask import Flask, request, make_response

app = Flask(__name__)

# 配置（从环境变量读取）
WECHAT_TOKEN = os.environ.get('WECHAT_TOKEN', 'your_token')
WECHAT_APP_ID = os.environ.get('WECHAT_APP_ID', 'your_app_id')
WECHAT_APP_SECRET = os.environ.get('WECHAT_APP_SECRET', 'your_app_secret')

handler = WechatMessageHandler(WECHAT_TOKEN, WECHAT_APP_ID, WECHAT_APP_SECRET)

@app.route('/webhook/wechat', methods=['GET', 'POST'])
def wechat_webhook():
    """微信消息接收入口"""
    
    if request.method == 'GET':
        # 微信服务器验证
        signature = request.args.get('signature', '')
        timestamp = request.args.get('timestamp', '')
        nonce = request.args.get('nonce', '')
        echostr = request.args.get('echostr', '')
        
        if handler.verify_signature(signature, timestamp, nonce):
            return echostr
        else:
            return 'fail'
    
    elif request.method == 'POST':
        # 接收消息
        xml_data = request.data.decode('utf-8')
        
        # 解析消息类型
        message = handler.parse_xml_message(xml_data)
        msg_type = message.get('MsgType', '')
        
        if msg_type == 'text':
            # 文本消息
            reply_xml = handler.handle_message(xml_data)
            response = make_response(reply_xml)
            response.content_type = 'application/xml'
            return response
        
        elif msg_type == 'event':
            # 事件消息
            reply_xml = handler.handle_event(xml_data)
            response = make_response(reply_xml)
            response.content_type = 'application/xml'
            return response
        
        else:
            return 'success'


if __name__ == '__main__':
    print("🚀 维宝宁销售话术对练 - 微信机器人服务启动")
    print("=" * 60)
    print(f"Token: {WECHAT_TOKEN[:10]}...")
    print(f"App ID: {WECHAT_APP_ID[:10]}..." if WECHAT_APP_ID else "App ID: 未配置")
    print("=" * 60)
    print("服务地址: http://0.0.0.0:5001/webhook/wechat")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5001, debug=False)
