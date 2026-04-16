#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
维宝宁销售话术对练 - AI智能版飞书机器人 (持久化版本)
集成LLM生成医生回复、实时评估、个性化反馈
支持5种医生角色，会话状态持久化存储
"""
import json
import os
import threading
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timedelta

# 导入AI对话引擎
from scripts.ai_dialogue_engine_persistent import create_session, process_message, get_session, delete_session
from scripts.start_practice import DOCTOR_PROFILES, SCENARIOS

app = Flask(__name__)

FEISHU_APP_ID = os.environ.get('FEISHU_APP_ID', 'cli_a938ac2a24391bcb')
FEISHU_APP_SECRET = os.environ.get('FEISHU_APP_SECRET', '')

# 数据目录
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

# 5种医生角色
ROLES = {
    '1': ('主任级专家', '学术型', '⭐⭐⭐⭐⭐'),
    '2': ('科室主任', '管理型', '⭐⭐⭐⭐'),
    '3': ('主治医师', '实用型', '⭐⭐⭐'),
    '4': ('住院医师', '学习型', '⭐⭐'),
    '5': ('带组专家', '影响力型', '⭐⭐⭐⭐⭐')
}

SCENARIOS_MAP = {
    '1': '完整拜访流程',
    '2': '价格异议处理',
    '3': '竞品对比应对',
    '4': '安全性质疑',
    '5': '学术型专家拜访'
}


def get_token():
    """获取飞书tenant_access_token"""
    try:
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        resp = requests.post(url, json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}, timeout=10)
        return resp.json().get("tenant_access_token")
    except:
        return None


def send_msg(open_id, msg_id, text):
    """发送消息到飞书"""
    def do():
        try:
            token = get_token()
            if not token:
                return
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            if msg_id:
                url = f"https://open.feishu.cn/open-apis/im/v1/messages/{msg_id}/reply"
                data = {"msg_type": "text", "content": json.dumps({"text": text})}
            else:
                url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"
                data = {"receive_id": open_id, "msg_type": "text", "content": json.dumps({"text": text})}
            requests.post(url, headers=headers, json=data, timeout=10)
        except:
            pass
    threading.Thread(target=do, daemon=True).start()


def send_card(open_id, msg_id, card_data):
    """发送卡片消息"""
    def do():
        try:
            token = get_token()
            if not token:
                return
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            if msg_id:
                url = f"https://open.feishu.cn/open-apis/im/v1/messages/{msg_id}/reply"
                data = {"msg_type": "interactive", "content": json.dumps(card_data)}
            else:
                url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"
                data = {"receive_id": open_id, "msg_type": "interactive", "content": json.dumps(card_data)}
            requests.post(url, headers=headers, json=data, timeout=10)
        except:
            pass
    threading.Thread(target=do, daemon=True).start()


def format_final_report_card(report):
    """格式化最终报告卡片"""
    overall_score = report.get('overall_score', 0)
    grade = report.get('grade', 'C')
    
    color_map = {
        'A': 'green',
        'B': 'blue',
        'C': 'orange',
        'D': 'red',
        'F': 'red'
    }
    color = color_map.get(grade, 'grey')
    
    # 维度得分
    dim_scores = report.get('dimension_scores', {})
    dim_text = f"""产品知识: {dim_scores.get('product_knowledge', 0):.1f}/10
话术规范: {dim_scores.get('script_standard', 0):.1f}/10
异议处理: {dim_scores.get('objection_handling', 0):.1f}/10
沟通礼仪: {dim_scores.get('communication', 0):.1f}/10
专业形象: {dim_scores.get('professional', 0):.1f}/10"""
    
    # 亮点
    strengths = report.get('strengths', [])
    strengths_text = "\n".join([f"🌟 {s}" for s in strengths[:3]]) if strengths else "继续保持！"
    
    # 改进点
    weaknesses = report.get('weaknesses', [])
    weaknesses_text = "\n".join([f"💡 {w}" for w in weaknesses[:3]]) if weaknesses else "表现不错！"
    
    # 学习建议
    suggestions = report.get('suggestions', [])
    suggestions_text = "\n".join([f"📚 {s}" for s in suggestions[:3]]) if suggestions else "继续保持！"
    
    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "🎉 对练完成！最终评估报告"},
            "template": color
        },
        "elements": [
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**综合评分: {overall_score}/10 (等级 {grade})**"}
            },
            {"tag": "hr"},
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**📊 各维度得分:**\n{dim_text}"}
            },
            {"tag": "hr"},
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**🌟 亮点:**\n{strengths_text}"}
            },
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**📝 待改进:**\n{weaknesses_text}"}
            },
            {"tag": "hr"},
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**💡 学习建议:**\n{suggestions_text}"}
            },
            {"tag": "hr"},
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**📝 总体评价:**\n{report.get('overall_feedback', '')}"}
            },
            {"tag": "hr"},
            {
                "tag": "note",
                "elements": [{"tag": "plain_text", "content": "发送【开始练习】可以重新开始对练"}]
            }
        ]
    }
    
    return card


def handle_msg(text, user_id, msg_id=None):
    """处理用户消息"""
    text = text.strip()
    
    # 开始练习
    if text in ['开始练习', 'start', '开始', '开始对练']:
        # 清除旧会话
        delete_session(user_id)
        
        return """👋 欢迎开始维宝宁销售话术对练（AI智能版）！

请选择医生角色（回复数字）：
1️⃣ 主任级专家 ⭐⭐⭐⭐⭐ - 学术型、严谨、注重证据
2️⃣ 科室主任 ⭐⭐⭐⭐ - 管理型、务实、时间紧
3️⃣ 主治医师 ⭐⭐⭐ - 实用型、经验导向
4️⃣ 住院医师 ⭐⭐ - 学习型、听从上级
5️⃣ 带组专家 ⭐⭐⭐⭐⭐ - 影响力型、决策权高

💡 提示：不同医生类型有不同的关注点和提问风格，AI会根据你的回答智能调整对话。"""
    
    # 结束练习
    if text in ['结束', 'stop', '退出']:
        delete_session(user_id)
        return "对练已结束。发送【开始练习】重新开始"
    
    # 帮助
    if text in ['帮助', 'help', '?']:
        return """📖 维宝宁销售话术对练 - 使用帮助

【开始练习】 - 开始新的对练
【结束】 - 结束当前对练
【帮助】 - 查看帮助信息

**对练流程：**
1. 选择医生角色（1-5）
2. AI医生会根据你的回答智能回复
3. 每轮都会给出评分和反馈
4. 完成8轮后生成最终报告

**评分维度：**
- 产品知识（25%）
- 话术规范（20%）
- 异议处理（25%）
- 沟通礼仪（15%）
- 专业形象（15%）

💡 尽量使用专业术语和产品数据，AI会评估你的回答质量！"""
    
    # 检查是否有活跃会话
    engine = get_session(user_id)
    
    # 选择医生角色
    if text in ROLES and not engine:
        role_name, role_type, stars = ROLES[text]
        
        # 创建AI会话
        scenario = '完整拜访流程'  # 默认场景
        session_id, engine = create_session(user_id, role_name, scenario)
        
        # 获取医生开场白
        doctor_opening = engine.get_doctor_response("你好，我是丽珠医药的代表，想跟您介绍一下我们的新产品。")
        
        return f"""✅ 已选择：{role_name} {stars}
类型：{role_type}
难度：{stars}

🎬 对练开始！

👨‍⚕️ **医生说：**
{doctor_opening}

💬 **请回复你的开场白...**

---
💡 提示：这是第1轮（共8轮），AI会根据你的回答智能调整后续对话。"""
    
    # 如果没有活跃会话
    if not engine:
        return "发送【开始练习】开始新的对练，或发送【帮助】查看使用说明"
    
    # 处理用户回答
    result = process_message(user_id, text)
    
    if 'error' in result:
        return f"出错了：{result['error']}"
    
    # 获取评估结果
    evaluation = result['evaluation']
    doctor_response = result['doctor_response']
    round_num = result['round']
    
    # 构建回复
    reply_text = f"""👨‍⚕️ **医生说：**
{doctor_response}

---
📊 **第{round_num}轮评分：{evaluation['total_score']}/10（等级{evaluation['grade']}）**
💬 **反馈：** {evaluation['feedback']}"""
    
    # 如果不是最后一轮，提示下一轮
    if not result.get('is_complete'):
        reply_text += f"""

💬 **请回复第{round_num + 1}轮...**
（还剩{8 - round_num}轮）"""
        return reply_text
    else:
        # 对练完成，返回最终报告
        final_report = result['final_report']
        
        # 清理会话
        delete_session(user_id)
        
        # 返回文本摘要
        summary = f"""🎉 对练完成！

📊 **综合评分：{final_report['overall_score']}/10（等级{final_report['grade']}）**

{final_report['overall_feedback']}

发送【开始练习】可以重新开始对练。"""
        
        return summary


@app.route('/')
def index():
    return jsonify({'status': 'ok', 'version': 'ai-persistent-v2.1', 'features': ['AI智能对话', '实时评估', '个性化反馈', '会话持久化', '5种医生角色']})


@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})


@app.route('/webhook/feishu', methods=['POST', 'GET'])
@app.route('/api/feishu/chat', methods=['POST', 'GET'])  # 兼容旧版webhook地址
def webhook():
    try:
        if request.method == 'GET':
            return jsonify({'status': 'ok'})
        
        data = request.get_json() or {}
        
        # 处理挑战验证
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
                
                # 清理@机器人的内容
                text = text.replace('@_user_1', '').replace('@维宝宁销售训练助手', '').strip()
                
                user_id = sender.get('sender_id', {}).get('open_id', '')
                msg_id = message.get('message_id', '')
                
                if text and user_id:
                    reply = handle_msg(text, user_id, msg_id)
                    send_msg(user_id, msg_id, reply)
        
        return jsonify({'status': 'ok'})
    except Exception as e:
        import traceback
        print(f"Error: {e}")
        print(traceback.format_exc())
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/practice/start', methods=['POST'])
def api_start_practice():
    """API：开始对练"""
    data = request.get_json() or {}
    user_id = data.get('user_id', 'anonymous')
    doctor_type = data.get('doctor_type', '科室主任')
    scenario = data.get('scenario', '完整拜访流程')
    style_tags = data.get('style_tags', [])
    
    session_id, engine = create_session(user_id, doctor_type, scenario, style_tags)
    
    # 获取医生开场白
    doctor_opening = engine.get_doctor_response("你好，我是丽珠医药的代表。")
    
    return jsonify({
        'status': 'ok',
        'session_id': session_id,
        'doctor_type': doctor_type,
        'scenario': scenario,
        'doctor_opening': doctor_opening,
        'round': 1,
        'total_rounds': 8
    })


@app.route('/api/practice/message', methods=['POST'])
def api_send_message():
    """API：发送消息"""
    data = request.get_json() or {}
    user_id = data.get('user_id')
    user_message = data.get('message', '')
    
    if not user_id:
        return jsonify({'status': 'error', 'message': '缺少user_id'}), 400
    
    result = process_message(user_id, user_message)
    
    if 'error' in result:
        return jsonify({'status': 'error', 'message': result['error']}), 400
    
    response = {
        'status': 'ok',
        'doctor_response': result['doctor_response'],
        'evaluation': result['evaluation'],
        'round': result['round'],
        'is_complete': result['is_complete']
    }
    
    if result.get('final_report'):
        response['final_report'] = result['final_report']
    
    return jsonify(response)


@app.route('/api/practice/report/<user_id>', methods=['GET'])
def api_get_report(user_id):
    """API：获取报告"""
    engine = get_session(user_id)
    if not engine:
        return jsonify({'status': 'error', 'message': '会话不存在'}), 404
    
    report = engine.generate_final_report()
    return jsonify({'status': 'ok', 'report': report})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
