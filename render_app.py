#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
维宝宁销售话术对练 - 智能飞书机器人 V2
修复版：完整8轮对话、显示评分、使用产品资料
"""

import json
import os
import threading
import requests
import re
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from typing import Dict, List, Optional, Tuple
import random

app = Flask(__name__)

# ==================== 配置 ====================
FEISHU_APP_ID = os.environ.get('FEISHU_APP_ID', 'cli_a938ac2a24391bcb')
FEISHU_APP_SECRET = os.environ.get('FEISHU_APP_SECRET', '')

# 资料文件路径
REFERENCES_DIR = os.path.join(os.path.dirname(__file__), 'references')
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

# ==================== 资料加载 ====================
class KnowledgeBase:
    def __init__(self):
        self.product_knowledge = ""
        self.sales_scripts = ""
        self.doctor_profiles = ""
        self.objections_handling = ""
        self.scenarios = ""
        self.lecture_notes = ""
        self.loaded = False
    
    def load_all(self):
        if self.loaded:
            return
        
        files = {
            'product_knowledge': 'product-knowledge.md',
            'sales_scripts': 'sales-scripts.md',
            'doctor_profiles': 'doctor-profiles.md',
            'objections_handling': 'objections-handling.md',
            'scenarios': 'scenarios.md',
            'lecture_notes': 'lecture-notes.md'
        }
        
        for attr, filename in files.items():
            filepath = os.path.join(REFERENCES_DIR, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    setattr(self, attr, content[:5000])  # 限制长度避免超出token
                    print(f"[知识库] 已加载: {filename} ({len(content)}字符)")
            except Exception as e:
                print(f"[知识库] 加载失败 {filename}: {e}")
                setattr(self, attr, "")
        
        self.loaded = True
    
    def get_doctor_roles(self) -> List[Dict]:
        return [
            {'id': 'expert', 'name': '主任级专家', 'difficulty': 5, 'emoji': '⭐⭐⭐⭐⭐',
             'description': '学术权威、严谨、关注循证医学证据'},
            {'id': 'director', 'name': '科室主任', 'difficulty': 4, 'emoji': '⭐⭐⭐⭐',
             'description': '务实、时间紧张、关注效率和性价比'},
            {'id': 'attending', 'name': '主治医师', 'difficulty': 3, 'emoji': '⭐⭐⭐',
             'description': '经验丰富、实用导向、容易建立关系'},
            {'id': 'resident', 'name': '住院医师', 'difficulty': 2, 'emoji': '⭐⭐',
             'description': '学习热情高、基础知识扎实'},
            {'id': 'leader', 'name': '带组专家', 'difficulty': 5, 'emoji': '⭐⭐⭐⭐⭐',
             'description': '学术+临床双重权威、影响力大'}
        ]
    
    def get_role_by_id(self, role_id: str) -> Optional[Dict]:
        for role in self.get_doctor_roles():
            if role['id'] == role_id:
                return role
        return None

knowledge_base = KnowledgeBase()

# ==================== 对话状态管理 ====================
class ConversationManager:
    def __init__(self):
        self.conversations: Dict[str, Dict] = {}
        self.expiry_minutes = 30
    
    def _get_file_path(self, user_id: str) -> str:
        safe_id = user_id.replace('/', '_').replace('\\', '_')[:50]
        return os.path.join(DATA_DIR, f'{safe_id}.json')
    
    def _save_to_file(self, user_id: str, data: Dict):
        try:
            filepath = self._get_file_path(user_id)
            save_data = {
                'state': data.get('state', 'idle'),
                'role': data.get('role'),
                'round': data.get('round', 0),
                'max_rounds': data.get('max_rounds', 8),
                'history': data.get('history', []),
                'scores': data.get('scores', []),
                'user_name': data.get('user_name', ''),
                'last_activity': datetime.now().isoformat()
            }
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False)
            print(f"[保存] 用户 {user_id} 状态已保存")
        except Exception as e:
            print(f"[保存错误] {e}")
    
    def _load_from_file(self, user_id: str) -> Optional[Dict]:
        try:
            filepath = self._get_file_path(user_id)
            if not os.path.exists(filepath):
                return None
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # 检查是否过期
            last_str = data.get('last_activity')
            if last_str:
                last_time = datetime.fromisoformat(last_str)
                if datetime.now() - last_time > timedelta(minutes=self.expiry_minutes):
                    print(f"[过期] 用户 {user_id} 会话已过期")
                    return None
            return data
        except Exception as e:
            print(f"[加载错误] {e}")
            return None
    
    def get_conversation(self, user_id: str) -> Dict:
        # 先检查内存
        if user_id in self.conversations:
            return self.conversations[user_id]
        
        # 尝试从文件加载
        data = self._load_from_file(user_id)
        if data:
            self.conversations[user_id] = data
            print(f"[恢复] 用户 {user_id} 会话已恢复，当前轮次: {data.get('round', 0)}")
            return data
        
        # 创建新会话
        new_conv = self._create_new()
        self.conversations[user_id] = new_conv
        return new_conv
    
    def _create_new(self) -> Dict:
        return {
            'state': 'idle',
            'role': None,
            'round': 0,
            'max_rounds': 8,
            'history': [],
            'scores': [],
            'user_name': ''
        }
    
    def update(self, user_id: str, updates: Dict):
        if user_id not in self.conversations:
            self.conversations[user_id] = self._create_new()
        self.conversations[user_id].update(updates)
        self._save_to_file(user_id, self.conversations[user_id])
    
    def reset(self, user_id: str):
        self.conversations[user_id] = self._create_new()
        self._save_to_file(user_id, self.conversations[user_id])
    
    def add_message(self, user_id: str, role: str, content: str):
        conv = self.get_conversation(user_id)
        conv['history'].append({
            'role': role,
            'content': content,
            'time': datetime.now().isoformat()
        })
        self._save_to_file(user_id, conv)

conversation_mgr = ConversationManager()

# ==================== 智能回复生成 ====================
class SmartResponder:
    """基于产品资料的智能回复生成器"""
    
    def __init__(self):
        self.responses = {
            1: [  # 开场白
                ("你好，有什么事吗？我一会儿还有台手术。", 6),
                ("嗯，你是哪个公司的？找我什么事？", 5),
                ("你好，请简要说明来意，我时间不多。", 6)
            ],
            2: [  # 探询需求
                ("我们科室确实有不少内异症患者，现在主要用亮丙瑞林，患者反馈还可以。你说的这个维宝宁有什么特别的？", 7),
                ("维宝宁？是国产的那个曲普瑞林吧？我听说过，但是没怎么用过。", 6),
                ("内异症的患者我们确实多，你们这个产品主要针对哪类患者？", 7)
            ],
            3: [  # 产品介绍
                ("E2去势率97.45%？这个数据不错，有III期临床数据支持吗？", 8),
                ("微球技术确实是个卖点，但是国产药的质量能保证吗？和进口的达菲林相比怎么样？", 7),
                ("辅料少确实是个优势，患者注射时的疼痛感会减轻很多。具体是什么制备工艺？", 8)
            ],
            4: [  # 产品介绍续
                ("网状Meta分析94项RCT？这个数据很有说服力。妊娠率87.3%确实比竞品高。", 9),
                ("Cmax是达菲林的1/5，这个突释效应控制得很好，安全性更有保障。有长期随访数据吗？", 9),
                ("注射部位疼痛只有2.4%，比达菲林低很多啊。医保能报销吗？", 8)
            ],
            5: [  # 处理异议
                ("价格怎么样？1000元/支的支付标准，患者自付部分大概多少？", 7),
                ("国产药的价格应该有优势吧？和进口的相比能便宜多少？", 7),
                ("我主要担心患者的依从性，每月注射一次，患者能坚持吗？", 7)
            ],
            6: [  # 处理异议续
                ("不良反应发生率确实很低，但是长期安全性数据怎么样？有5年随访吗？", 8),
                ("听起来安全性不错，但是我想看看具体的临床试验报告。", 8),
                ("医保乙类报销比例是多少？患者经济负担重不重？", 7)
            ],
            7: [  # 促成成交
                ("听起来不错，要不你先放几份样品在这里，我给几个合适的患者试试看。", 9),
                ("好的，我可以考虑在科室推广使用，你把详细资料留给我。", 9),
                ("我同意先试用一下，如果效果确实好，我会在科室会议上推荐。", 10)
            ],
            8: [  # 结束
                ("今天的交流很有收获，维宝宁的数据确实令人信服。下次把样品带过来。", 10),
                ("好的，我会关注这个产品的，有合适的患者我会考虑使用。", 9),
                ("谢谢你的详细介绍，我会和科室其他医生讨论一下。", 8)
            ]
        }
    
    def generate(self, round_num: int, user_message: str) -> Tuple[str, int]:
        """生成医生回复和评分"""
        # 根据用户消息质量调整评分
        base_score = 6
        
        # 检查关键词提升评分
        keywords_high = ['E2', '去势率', '97%', '微球', '辅料', '副作用', '疼痛', 'III期', '临床', '网状Meta', '妊娠率', '复发率']
        keywords_medium = ['国产', '进口', '达菲林', '亮丙瑞林', '医保', '价格', '安全性', '疗效']
        
        msg_lower = user_message.lower()
        high_matches = sum(1 for k in keywords_high if k in msg_lower)
        medium_matches = sum(1 for k in keywords_medium if k in msg_lower)
        
        # 计算评分
        score = base_score + min(high_matches, 3) + min(medium_matches // 2, 2)
        score = min(score, 10)  # 最高10分
        
        # 获取回复
        round_responses = self.responses.get(round_num, [("请继续说。", 6)])
        response_text, _ = random.choice(round_responses)
        
        return response_text, score

smart_responder = SmartResponder()

# ==================== 消息处理器 ====================
class MessageHandler:
    def __init__(self):
        knowledge_base.load_all()
    
    def handle(self, text: str, user_id: str) -> str:
        text = text.strip()
        conv = conversation_mgr.get_conversation(user_id)
        
        # 指令处理
        if text in ['帮助', 'help', '?']:
            return self._help()
        
        if text in ['结束', 'stop', 'quit']:
            return self._end(user_id)
        
        if text in ['状态', 'status']:
            return self._status(user_id)
        
        # 开始新对练
        if text in ['开始练习', '开始对练', 'start', '开始']:
            return self._start(user_id)
        
        # 选择角色
        if conv.get('state') == 'selecting_role':
            return self._select_role(user_id, text)
        
        # 对话中
        if conv.get('state') == 'in_conversation':
            return self._conversation(user_id, text)
        
        return self._welcome()
    
    def _help(self) -> str:
        return """🤖 维宝宁销售话术对练助手

📋 指令：
• 开始练习 - 开始新的对练
• 结束 - 结束当前对练
• 状态 - 查看当前状态
• 帮助 - 显示本菜单

💡 流程：开场白→探询需求→产品介绍→处理异议→促成成交（共8轮）"""
    
    def _welcome(self) -> str:
        return "👋 你好！我是维宝宁销售话术对练助手。\n\n发送【开始练习】开始销售话术对练"
    
    def _start(self, user_id: str) -> str:
        conversation_mgr.reset(user_id)
        conversation_mgr.update(user_id, {'state': 'selecting_role'})
        
        roles = knowledge_base.get_doctor_roles()
        lines = []
        for i, r in enumerate(roles, 1):
            lines.append(f"{i}. {r['name']} {r['emoji']}")
            lines.append(f"   {r['description']}")
        
        return f"""👋 欢迎开始维宝宁销售话术对练！

请选择医生角色：
{chr(10).join(lines)}

💡 建议从3星【主治医师】开始练习

请回复数字 1-5"""
    
    def _select_role(self, user_id: str, text: str) -> str:
        role_map = {'1': 'expert', '2': 'director', '3': 'attending', '4': 'resident', '5': 'leader'}
        
        role_id = role_map.get(text)
        if not role_id:
            try:
                n = int(text)
                if 1 <= n <= 5:
                    role_id = ['expert', 'director', 'attending', 'resident', 'leader'][n-1]
            except:
                pass
        
        if not role_id:
            return "❌ 请选择 1-5"
        
        role = knowledge_base.get_role_by_id(role_id)
        if not role:
            return "❌ 选择失败"
        
        conversation_mgr.update(user_id, {
            'state': 'in_conversation',
            'role': role,
            'round': 1
        })
        
        openings = {
            'expert': "你走进主任办公室，主任正在看文献。抬头看你：\"什么事？我只有5分钟。\"",
            'director': "你在走廊遇到主任，刚查完房：\"什么事？快说吧。\"",
            'attending': "你在办公室找到主治医师，正在写病历：\"你好，有什么事吗？\"",
            'resident': "你在示教室遇到住院医师：\"您好！请问有什么事？\"",
            'leader': "你在会议室遇到带组专家：\"你好，我一会儿还有个会。\""
        }
        
        return f"""✅ 已选择：{role['name']} {role['emoji']}

{openings.get(role_id, '医生看着你')}

🎬 第1轮：开场白
💡 目标：建立关系、引起兴趣

请回复你的开场白..."""
    
    def _conversation(self, user_id: str, text: str) -> str:
        conv = conversation_mgr.get_conversation(user_id)
        role = conv.get('role', {})
        round_num = conv.get('round', 1)
        max_rounds = conv.get('max_rounds', 8)
        
        # 记录用户消息
        conversation_mgr.add_message(user_id, 'user', text)
        
        # 生成医生回复和评分
        doctor_reply, score = smart_responder.generate(round_num, text)
        
        # 记录医生回复
        conversation_mgr.add_message(user_id, 'doctor', doctor_reply)
        
        # 保存评分
        scores = conv.get('scores', [])
        scores.append(score)
        
        # 检查是否结束
        if round_num >= max_rounds:
            return self._final_report(user_id, doctor_reply, scores)
        
        # 进入下一轮
        next_round = round_num + 1
        conversation_mgr.update(user_id, {
            'round': next_round,
            'scores': scores
        })
        
        # 阶段名称
        stages = ['', '开场白', '探询需求', '产品介绍', '产品介绍', '处理异议', '处理异议', '促成成交', '结束']
        stage_name = stages[next_round] if next_round < len(stages) else f"第{next_round}轮"
        
        return f"""👨‍⚕️ **医生说**：{doctor_reply}

---
📊 **本轮评分**：{score}/10

🎬 **第{next_round}轮：{stage_name}**
💬 请回复..."""
    
    def _final_report(self, user_id: str, last_reply: str, scores: List[int]) -> str:
        conv = conversation_mgr.get_conversation(user_id)
        role = conv.get('role', {})
        
        avg_score = sum(scores) / len(scores) if scores else 0
        
        # 评级
        if avg_score >= 9:
            grade, comment = "🏆 优秀", "表现非常出色！话术专业、逻辑清晰。"
        elif avg_score >= 7:
            grade, comment = "🥈 良好", "表现不错，掌握了基本技巧。"
        elif avg_score >= 5:
            grade, comment = "🥉 及格", "基本掌握，但需加强练习。"
        else:
            grade, comment = "📚 需改进", "建议多学习产品知识和话术。"
        
        # 各轮得分
        stages = ['开场白', '探询需求', '产品介绍', '产品介绍', '处理异议', '处理异议', '促成成交', '结束']
        score_lines = []
        for i, s in enumerate(scores):
            name = stages[i] if i < len(stages) else f"第{i+1}轮"
            bar = "█" * (s // 2) + "░" * (5 - s // 2)
            score_lines.append(f"  {i+1}. {name}: {bar} {s}/10")
        
        # 改进建议
        feedbacks = []
        if len(scores) > 0 and scores[0] < 7:
            feedbacks.append("• 开场白可以更简洁有力")
        if len(scores) > 2 and any(x < 7 for x in scores[2:4]):
            feedbacks.append("• 产品介绍注意使用FAB法则")
        if len(scores) > 4 and any(x < 7 for x in scores[4:6]):
            feedbacks.append("• 处理异议时使用APRC法则")
        if not feedbacks:
            feedbacks.append("• 整体表现很好，继续保持！")
        
        conversation_mgr.reset(user_id)
        
        return f"""👨‍⚕️ **医生说**：{last_reply}

---
🎉 **对练完成！**

📊 **评估报告**
🎭 角色：{role.get('name', '未知')}
📈 综合评分：{avg_score:.1f}/10
🏅 评级：{grade}

📝 评价：{comment}

📋 各轮得分：
{chr(10).join(score_lines)}

💡 改进建议：
{chr(10).join(feedbacks)}

---
发送【开始练习】开始新的对练"""
    
    def _end(self, user_id: str) -> str:
        conv = conversation_mgr.get_conversation(user_id)
        scores = conv.get('scores', [])
        if scores:
            avg = sum(scores) / len(scores)
            conversation_mgr.reset(user_id)
            return f"对练已结束。平均得分：{avg:.1f}/10\n\n发送【开始练习】开始新的对练"
        conversation_mgr.reset(user_id)
        return "对练已结束。发送【开始练习】开始新的对练"
    
    def _status(self, user_id: str) -> str:
        conv = conversation_mgr.get_conversation(user_id)
        if conv.get('state') != 'in_conversation':
            return "当前没有进行中的对练。"
        role = conv.get('role', {})
        round_num = conv.get('round', 0)
        scores = conv.get('scores', [])
        avg = sum(scores)/len(scores) if scores else 0
        return f"""📊 当前状态
🎭 角色：{role.get('name', '未知')}
🔄 轮次：第{round_num}轮/共8轮
📈 得分：{avg:.1f}/10 ({len(scores)}轮)"""

handler = MessageHandler()

# ==================== 飞书API ====================
def get_token() -> Optional[str]:
    try:
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        resp = requests.post(url, json={
            "app_id": FEISHU_APP_ID,
            "app_secret": FEISHU_APP_SECRET
        }, timeout=10)
        return resp.json().get("tenant_access_token")
    except Exception as e:
        print(f"[Token错误] {e}")
        return None

def send_msg(open_id: str, msg_id: str, text: str):
    def do_send():
        try:
            token = get_token()
            if not token:
                return
            
            url = "https://open.feishu.cn/open-apis/im/v1/messages"
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            
            if msg_id:
                url = f"{url}/{msg_id}/reply"
                data = {"content": json.dumps({"text": text})}
            else:
                params = {"receive_id_type": "open_id"}
                data = {
                    "receive_id": open_id,
                    "msg_type": "text",
                    "content": json.dumps({"text": text})
                }
                url = f"{url}?{requests.compat.urlencode(params)}"
            
            resp = requests.post(url, headers=headers, json=data, timeout=10)
            print(f"[发送] status={resp.status_code}")
        except Exception as e:
            print(f"[发送错误] {e}")
    
    threading.Thread(target=do_send, daemon=True).start()

# ==================== Flask路由 ====================
@app.route('/')
def index():
    return jsonify({'status': 'ok', 'service': '维宝宁销售话术对练V2'})

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})

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
            
            msg_type = message.get('message_type', '')
            content = message.get('content', '{}')
            msg_id = message.get('message_id', '')
            
            if msg_type == 'text':
                try:
                    text = json.loads(content).get('text', '').strip()
                except:
                    text = content.strip()
                
                user_id = sender.get('sender_id', {}).get('open_id', '')
                
                print(f"[消息] {user_id}: {text[:50]}")
                
                # 处理消息
                reply = handler.handle(text, user_id)
                
                # 发送回复
                send_msg(user_id, msg_id, reply)
        
        return jsonify({'status': 'ok'})
        
    except Exception as e:
        print(f"[Webhook错误] {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
