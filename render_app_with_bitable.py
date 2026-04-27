#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
维宝宁销售话术对练 - 支持数据持久化到飞书多维表格
"""
import json
import os
import threading
import requests
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

# 飞书应用配置
FEISHU_APP_ID = os.environ.get('FEISHU_APP_ID', 'cli_a938ac2a24391bcb')
FEISHU_APP_SECRET = os.environ.get('FEISHU_APP_SECRET', '')

# 多维表格配置
BITABLE_APP_TOKEN = os.environ.get('BITABLE_APP_TOKEN', 'W0JRbfMx9aBorzsC9cocnH6gnOd')
BITABLE_TABLE_ID = os.environ.get('BITABLE_TABLE_ID', 'tblLXaEzCzK9x8cB')

# 内存缓存（用于活跃会话）
users = {}

# 医生角色配置
ROLES = {
    '1': ('主任级专家', '⭐⭐⭐⭐⭐'),
    '2': ('科室主任', '⭐⭐⭐⭐'),
    '3': ('主治医师', '⭐⭐⭐'),
    '4': ('住院医师', '⭐⭐'),
    '5': ('带组专家', '⭐⭐⭐⭐⭐')
}

# 对话流程
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

# ==================== 飞书 API 工具函数 ====================

def get_tenant_access_token():
    """获取飞书租户访问令牌"""
    try:
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        resp = requests.post(url, json={
            "app_id": FEISHU_APP_ID,
            "app_secret": FEISHU_APP_SECRET
        }, timeout=10)
        result = resp.json()
        if result.get("code") == 0:
            return result.get("tenant_access_token")
        else:
            print(f"[Token错误] {result}")
            return None
    except Exception as e:
        print(f"[Token异常] {e}")
        return None


def send_feishu_message(open_id, msg_id, text):
    """发送飞书消息（异步）"""
    def do_send():
        try:
            token = get_tenant_access_token()
            if not token:
                return
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            if msg_id:
                # 回复消息
                url = f"https://open.feishu.cn/open-apis/im/v1/messages/{msg_id}/reply"
                data = {"content": json.dumps({"text": text})}
            else:
                # 发送新消息
                url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"
                data = {
                    "receive_id": open_id,
                    "msg_type": "text",
                    "content": json.dumps({"text": text})
                }
            
            resp = requests.post(url, headers=headers, json=data, timeout=10)
            print(f"[发送消息] {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"[发送消息异常] {e}")
    
    threading.Thread(target=do_send, daemon=True).start()


def save_training_record(user_id, user_name, role, scores, total_score):
    """
    保存训练记录到多维表格
    """
    def do_save():
        try:
            token = get_tenant_access_token()
            if not token:
                print("[保存记录] 无法获取token")
                return
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            # 构建记录数据 - 匹配实际表格字段
            now = datetime.now()
            now_timestamp = int(now.timestamp() * 1000)  # 毫秒时间戳
            
            record_data = {
                "fields": {
                    "用户ID": user_id,
                    "用户姓名": user_name or "未知用户",
                    "医生角色": role,
                    "开始时间": now_timestamp,
                    "结束时间": now_timestamp,
                    "总评分": total_score,
                    "各轮得分": json.dumps(scores),
                    "对话轮数": len(scores),
                    "完成状态": "已完成"
                }
            }
            
            url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{BITABLE_APP_TOKEN}/tables/{BITABLE_TABLE_ID}/records"
            resp = requests.post(url, headers=headers, json=record_data, timeout=10)
            result = resp.json()
            
            if result.get("code") == 0:
                print(f"[保存记录成功] 用户: {user_id}, 分数: {total_score}")
            else:
                print(f"[保存记录失败] {result}")
        
        except Exception as e:
            print(f"[保存记录异常] {e}")
    
    threading.Thread(target=do_save, daemon=True).start()


def get_user_name(user_id):
    """获取用户姓名"""
    try:
        token = get_tenant_access_token()
        if not token:
            return None
        
        headers = {"Authorization": f"Bearer {token}"}
        url = f"https://open.feishu.cn/open-apis/contact/v3/users/{user_id}"
        params = {"user_id_type": "open_id"}
        
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        result = resp.json()
        
        if result.get("code") == 0:
            user = result.get("data", {}).get("user", {})
            return user.get("name")
        return None
    except:
        return None


# ==================== 业务逻辑 ====================

def handle_message(text, user_id):
    """处理用户消息"""
    text = text.strip()
    
    # 开始练习
    if text in ['开始练习', 'start', '开始']:
        users[user_id] = {
            'step': 0,
            'role': None,
            'role_name': None,
            'scores': [],
            'user_name': None
        }
        return "👋 欢迎开始维宝宁销售话术对练！\n\n请选择医生角色（回复数字）：\n1. 主任级专家 ⭐⭐⭐⭐⭐\n2. 科室主任 ⭐⭐⭐⭐\n3. 主治医师 ⭐⭐⭐\n4. 住院医师 ⭐⭐\n5. 带组专家 ⭐⭐⭐⭐⭐"
    
    # 结束练习
    if text in ['结束', 'stop']:
        if user_id in users:
            del users[user_id]
        return "对练已结束。发送【开始练习】重新开始"
    
    # 获取用户会话
    u = users.get(user_id)
    if not u:
        return "发送【开始练习】开始"
    
    # 选择角色阶段
    if u['step'] == 0:
        if text in ROLES:
            role_name, stars = ROLES[text]
            u['role'] = text
            u['role_name'] = role_name
            u['step'] = 1
            
            # 异步获取用户姓名
            def fetch_name():
                name = get_user_name(user_id)
                if name:
                    u['user_name'] = name
            threading.Thread(target=fetch_name, daemon=True).start()
            
            doctor_text = DIALOGUE[0]
            u['scores'].append(6)  # 初始分
            
            return f"✅ 已选择：{role_name} {stars}\n\n🎬 第1轮：开场白\n\n👨‍⚕️ 医生说：{doctor_text}\n\n💬 请回复你的开场白..."
        return "请选择 1-5"
    
    # 对练进行中
    step = u['step']
    
    # 评分逻辑（修正：曲普瑞林，不是亮丙瑞林）
    keywords = ['E2', '去势率', '97%', '微球', '辅料', '副作用', '疼痛', '临床', 
                'Meta', '妊娠率', '复发率', '价格', '医保', '安全性', '样品', '试用',
                '子宫内膜异位症', '内异症', 'GnRH', '曲普瑞林', '地诺孕素', '零突释']
    matches = sum(1 for k in keywords if k in text)
    user_score = min(6 + matches, 10)
    u['scores'].append(user_score)
    
    # 检查是否完成
    if step >= 8:
        avg = sum(u['scores']) / len(u['scores'])
        
        # 生成评分报告
        lines = []
        for i, s in enumerate(u['scores']):
            name = STAGES[i]
            bar = '█' * (s // 2) + '░' * (5 - s // 2)
            lines.append(f"  {i+1}. {name}: {bar} {s}/10")
        
        # 保存到多维表格
        save_training_record(
            user_id=user_id,
            user_name=u.get('user_name'),
            role=u.get('role_name', '未知'),
            scores=u['scores'],
            total_score=round(avg, 1)
        )
        
        # 清理内存
        del users[user_id]
        
        return f"🎉 对练完成！\n\n📊 综合评分：{avg:.1f}/10\n\n📋 各轮得分：\n" + "\n".join(lines) + "\n\n✅ 训练记录已保存到多维表格\n\n发送【开始练习】重新开始"
    
    # 继续下一轮
    u['step'] = step + 1
    doctor_text = DIALOGUE[step]
    
    return f"👨‍⚕️ 医生说：{doctor_text}\n\n📊 上轮评分：{user_score}/10\n\n🎬 第{step+1}轮：{STAGES[step]}\n💬 请回复..."


# ==================== Flask 路由 ====================

@app.route('/')
def index():
    return jsonify({
        'status': 'ok',
        'version': 'bitable-v1',
        'features': ['training', 'bitable_storage']
    })


@app.route('/webhook/feishu', methods=['POST', 'GET'])
def webhook():
    """飞书 webhook 回调"""
    try:
        # GET 健康检查
        if request.method == 'GET':
            return jsonify({'status': 'ok'})
        
        data = request.get_json() or {}
        
        # 处理挑战验证
        if 'challenge' in data:
            return jsonify({'challenge': data['challenge']})
        
        header = data.get('header', {})
        event = data.get('event', {})
        
        # 处理消息接收事件
        if header.get('event_type') == 'im.message.receive_v1':
            message = event.get('message', {})
            sender = event.get('sender', {})
            
            if message.get('message_type') == 'text':
                # 解析消息内容
                try:
                    content = json.loads(message.get('content', '{}'))
                    text = content.get('text', '').strip()
                except:
                    text = message.get('content', '').strip()
                
                user_id = sender.get('sender_id', {}).get('open_id', '')
                msg_id = message.get('message_id', '')
                
                # 处理消息
                reply = handle_message(text, user_id)
                send_feishu_message(user_id, msg_id, reply)
        
        return jsonify({'status': 'ok'})
    
    except Exception as e:
        print(f"[Webhook异常] {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
