#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书 API 客户端
用于发送消息、管理会话等
"""

import json
import requests
import os
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

class FeishuAPI:
    """飞书开放平台 API 客户端"""
    
    BASE_URL = "https://open.feishu.cn/open-apis"
    
    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self._tenant_access_token = None
        self._token_expires_at = None
    
    def _get_tenant_access_token(self) -> Optional[str]:
        """获取租户访问令牌"""
        # 检查缓存
        if self._tenant_access_token and self._token_expires_at and datetime.now() < self._token_expires_at:
            return self._tenant_access_token
        
        url = f"{self.BASE_URL}/auth/v3/tenant_access_token/internal"
        
        payload = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            result = response.json()
            
            if result.get("code") == 0:
                self._tenant_access_token = result.get("tenant_access_token")
                expires_in = result.get("expire", 7200)
                # 提前5分钟过期
                self._token_expires_at = datetime.now() + timedelta(seconds=expires_in - 300)
                return self._tenant_access_token
            else:
                print(f"[飞书API错误] 获取token失败: {result}")
                return None
        except Exception as e:
            print(f"[飞书API错误] 请求异常: {e}")
            return None
    
    def send_text_message(self, receive_id: str, text: str, receive_id_type: str = "open_id") -> Dict[str, Any]:
        """
        发送文本消息
        
        Args:
            receive_id: 接收者ID
            text: 消息文本
            receive_id_type: ID类型 (open_id/user_id/union_id/chat_id/email)
        
        Returns:
            API 响应结果
        """
        token = self._get_tenant_access_token()
        if not token:
            return {"error": "Failed to get access token"}
        
        url = f"{self.BASE_URL}/im/v1/messages"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        params = {
            "receive_id_type": receive_id_type
        }
        
        content = json.dumps({"text": text})
        
        payload = {
            "receive_id": receive_id,
            "msg_type": "text",
            "content": content
        }
        
        try:
            response = requests.post(url, headers=headers, params=params, json=payload, timeout=10)
            result = response.json()
            
            if result.get("code") == 0:
                return {"success": True, "data": result.get("data")}
            else:
                return {"success": False, "error": result.get("msg"), "code": result.get("code")}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def reply_message(self, message_id: str, text: str) -> Dict[str, Any]:
        """
        回复消息
        
        Args:
            message_id: 要回复的消息ID
            text: 回复内容
        
        Returns:
            API 响应结果
        """
        token = self._get_tenant_access_token()
        if not token:
            return {"error": "Failed to get access token"}
        
        url = f"{self.BASE_URL}/im/v1/messages/{message_id}/reply"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        content = json.dumps({"text": text})
        
        payload = {
            "content": content,
            "msg_type": "text"
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            result = response.json()
            
            if result.get("code") == 0:
                return {"success": True, "data": result.get("data")}
            else:
                return {"success": False, "error": result.get("msg"), "code": result.get("code")}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_user_info(self, user_id: str, user_id_type: str = "open_id") -> Dict[str, Any]:
        """获取用户信息"""
        token = self._get_tenant_access_token()
        if not token:
            return {"error": "Failed to get access token"}
        
        url = f"{self.BASE_URL}/contact/v3/users/{user_id}"
        
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        params = {
            "user_id_type": user_id_type
        }
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            result = response.json()
            
            if result.get("code") == 0:
                return {"success": True, "data": result.get("data", {}).get("user", {})}
            else:
                return {"success": False, "error": result.get("msg")}
        except Exception as e:
            return {"success": False, "error": str(e)}


# 全局 API 客户端实例
_feishu_api = None

def get_feishu_api() -> FeishuAPI:
    """获取飞书 API 客户端（单例）"""
    global _feishu_api
    
    if _feishu_api is None:
        app_id = os.environ.get('FEISHU_APP_ID', '')
        app_secret = os.environ.get('FEISHU_APP_SECRET', '')
        
        if app_id and app_secret:
            _feishu_api = FeishuAPI(app_id, app_secret)
        else:
            print("[警告] 飞书 App ID 或 App Secret 未配置")
    
    return _feishu_api
