#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书 API 客户端
用于发送消息、管理会话等
"""

import json
import requests
import os
from datetime import datetime, timedelta

class FeishuAPI:
    """飞书开放平台 API 客户端"""
    
    BASE_URL = "https://open.feishu.cn/open-apis"
    
    def __init__(self, app_id, app_secret):
        self.app_id = app_id
        self.app_secret = app_secret
        self._token = None
        self._token_expires = None
    
    def _get_token(self):
        """获取租户访问令牌"""
        if self._token and self._token_expires and datetime.now() < self._token_expires:
            return self._token
        
        url = f"{self.BASE_URL}/auth/v3/tenant_access_token/internal"
        payload = {"app_id": self.app_id, "app_secret": self.app_secret}
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            result = response.json()
            
            if result.get("code") == 0:
                self._token = result.get("tenant_access_token")
                expires_in = result.get("expire", 7200)
                self._token_expires = datetime.now() + timedelta(seconds=expires_in - 300)
                return self._token
            return None
        except:
            return None
    
    def send_text_message(self, receive_id, text, chat_type='open_id'):
        """发送文本消息
        chat_type: 'open_id'表示单聊，'chat_id'表示群聊
        """
        token = self._get_token()
        if not token:
            return {"error": "Failed to get token"}
        
        url = f"{self.BASE_URL}/im/v1/messages"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        params = {"receive_id_type": chat_type}
        content = json.dumps({"text": text})
        payload = {"receive_id": receive_id, "msg_type": "text", "content": content}
        
        try:
            response = requests.post(url, headers=headers, params=params, json=payload, timeout=10)
            result = response.json()
            if result.get("code") == 0:
                return {"success": True}
            return {"success": False, "error": result.get("msg")}
        except Exception as e:
            return {"success": False, "error": str(e)}

def get_feishu_api():
    """获取飞书 API 客户端"""
    app_id = os.environ.get('FEISHU_APP_ID', '')
    # 兼容两种变量名
    app_secret = os.environ.get('FEISHU_APP_SECRET', '') or os.environ.get('FEISHU_SECRET', '')
    if app_id and app_secret:
        return FeishuAPI(app_id, app_secret)
    return None
