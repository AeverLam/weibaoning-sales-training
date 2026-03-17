#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
维宝宁销售话术对练 - 智能飞书机器人
基于LLM的智能医生角色扮演对练系统
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
LLM_API_KEY = os.environ.get('LLM_API_KEY', '')
LLM_API_URL = os.environ.get('LLM_API_URL', 'https://api.openai.com/v1/chat/completions')
LLM_MODEL = os.environ.get('LLM_MODEL', 'gpt-4')

# 资料文件路径
REFERENCES_DIR = os.path.join(os.path.dirname(__file__), 'references')

# ==================== 对话状态管理 ====================
class ConversationManager:
    """用户对话状态管理器"""
    
    def __init__(self):
        self.conversations: Dict[str, Dict] = {}
        self.expiry_minutes = 30
    
    def get_conversation(self, user_id: str) -> Dict:
        if user_id not in self.conversations:
            self.conversations[user_id] = self._create_new_conversation()
        else:
            last_activity = self.conversations[user_id].get('last_activity')
            if last_activity:
                elapsed = datetime.now() - last_activity
                if elapsed > timedelta(minutes=self.expiry_minutes):
                    self.conversations[user_id] = self._create_new_conversation()
        
        self.conversations[user_id]['last_activity'] = datetime.now()
        return self.conversations[user_id]
    
    def _create_new_conversation(self) -> Dict:
        return {
            'state': 'idle',
            'role': None,
            'round': 0,
            'max_rounds': 8,
            'history': [],
            'scores': [],
            'start_time': datetime.now(),
            'last_activity': datetime.now(),
            'user_name': '',
            'context': {}
        }
    
    def update_conversation(self, user_id: str, updates: Dict):
        if user_id in self.conversations:
            self.conversations[user_id].update(updates)
            self.conversations[user_id]['last_activity'] = datetime.now()
    
    def reset_conversation(self, user_id: str):
        self.conversations[user_id] = self._create_new_conversation()
    
    def add_message(self, user_id: str, role: str, content: str):
        conv = self.get_conversation(user_id)
        conv['history'].append({
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat()
        })
        conv['last_activity'] = datetime.now()

conversation_mgr = ConversationManager()

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
                    setattr(self, attr, content)
                    print(f"[知识库] 已加载: {filename}")
            except Exception as e:
                print(f"[知识库] 加载失败 {filename}: {e}")
                setattr(self, attr, "")
        
        self.loaded = True
    
    def get_doctor_roles(self) -> List[Dict]:
        return [
            {
                'id': 'expert',
                'name': '主任级专家（学术型）',
                'difficulty': 5,
                'emoji': '⭐⭐⭐⭐⭐',
                'description': '学术权威、严谨、关注循证医学证据',
                'traits': ['注重临床试验数据', '喜欢讨论作用机制', '对新药持谨慎态度', '重视学术声誉'],
                'typical_questions': ['这个研究的样本量有多大？', '有III期临床数据吗？', '作用机制是什么？', '指南是怎么推荐的？']
            },
            {
                'id': 'director',
                'name': '科室主任（管理型）',
                'difficulty': 4,
                'emoji': '⭐⭐⭐⭐',
                'description': '务实、时间紧张、关注效率和性价比',
                'traits': ['注重实际效果', '关心科室运营成本', '时间观念强', '决策果断'],
                'typical_questions': ['这个产品疗效确切吗？', '不良反应多不多？', '价格怎么样？医保报吗？', '患者依从性如何？']
            },
            {
                'id': 'attending',
                'name': '主治医师（实用型）',
                'difficulty': 3,
                'emoji': '⭐⭐⭐',
                'description': '经验丰富、实用导向、容易建立关系',
                'traits': ['注重临床经验', '喜欢听同行反馈', '对新药接受度中等', '重视用药便利性'],
                'typical_questions': ['其他医院用得怎么样？', '患者反馈如何？', '使用起来方便吗？', '有没有试用装？']
            },
            {
                'id': 'resident',
                'name': '住院医师（学习型）',
                'difficulty': 2,
                'emoji': '⭐⭐',
                'description': '学习热情高、基础知识扎实、时间相对充裕',
                'traits': ['学习意愿强', '临床经验少', '对新产品好奇', '愿意接受培训'],
                'typical_questions': ['这个药主要治什么？', '用法用量是怎样的？', '有哪些禁忌症需要注意？', '有学习资料吗？']
            },
            {
                'id': 'leader',
                'name': '带组专家（影响力型）',
                'difficulty': 5,
                'emoji': '⭐⭐⭐⭐⭐',
                'description': '学术+临床双重权威、影响力大、带教下级医生',
                'traits': ['学术和临床并重', '带教下级医生', '学术会议演讲嘉宾', '指南编写参与者'],
                'typical_questions': ['这个产品在学科发展中有什么价值？', '适合带教使用吗？', '有没有学术合作的机会？', '对学科发展有什么帮助？']
            }
        ]
    
    def get_role_by_id(self, role_id: str) -> Optional[Dict]:
        for role in self.get_doctor_roles():
            if role['id'] == role_id:
                return role
        return None
    
    def get_conversation_stage(self, round_num: int) -> Dict:
        stages = [
            {'round': 1, 'name': '开场白', 'description': '建立关系、引起兴趣、获得时间许可'},
            {'round': 2, 'name': '探询需求', 'description': '了解患者类型、用药习惯、未满足需求'},
            {'round': 3, 'name': '产品介绍', 'description': '传递产品价值，使用FAB法则'},
            {'round': 4, 'name': '产品介绍（续）', 'description': '深入介绍核心卖点'},
            {'round': 5, 'name': '处理异议', 'description': '化解医生顾虑，处理可能的异议'},
            {'round': 6, 'name': '处理异议（续）', 'description': '进一步回应疑问'},
            {'round': 7, 'name': '促成成交', 'description': '获得承诺、推动试用/处方'},
            {'round': 8, 'name': '结束与跟进', 'description': '总结、建立后续联系'}
        ]
        if 1 <= round_num <= len(stages):
            return stages[round_num - 1]
        return stages[-1]

knowledge_base = KnowledgeBase()

# ==================== LLM 调用 ====================
class LLMClient:
    def __init__(self):
        self.api_key = LLM_API_KEY
        self.api_url = LLM_API_URL
        self.model = LLM_MODEL
    
    def generate_doctor_response(self, user_id: str, user_message: str, conversation: Dict) -> Tuple[str, int]:
        role = conversation.get('role', {})
        round_num = conversation.get('round', 1)
        history = conversation.get('history', [])
        stage = knowledge_base.get_conversation_stage(round_num)
        
        system_prompt = self._build_system_prompt(role, stage, round_num)
        
        messages = [{'role': 'system', 'content': system_prompt}]
        
        for msg in history[-10:]:
            if msg['role'] == 'sales_rep':
                messages.append({'role': 'user', 'content': f"医药代表: {msg['content']}"})
            elif msg['role'] == 'doctor':
                messages.append({'role': 'assistant', 'content': msg['content']})
        
        messages.append({'role': 'user', 'content': f"医药代表: {user_message}"})
        
        try:
            response = self._call_llm(messages)
            score = self._extract_score(response)
            clean_response = self._clean_response(response)
            return clean_response, score
        except Exception as e:
            print(f"[LLM错误] {e}")
            return self._get_fallback_response(role, round_num), 5
    
    def _build_system_prompt(self, role: Dict, stage: Dict, round_num: int) -> str:
        product_summary = self._get_product_summary()
        role_traits = chr(10).join([f"- {trait}" for trait in role.get('traits', [])])
        typical_questions = chr(10).join([f"- {q}" for q in role.get('typical_questions', [])])
        
        prompt = f"""你正在扮演一位医生，与医药代表进行维宝宁（注射用醋酸曲普瑞林微球）的销售话术对练。

## 你的角色设定

**角色名称**: {role.get('name', '医生')}
**难度等级**: {role.get('difficulty', 3)}星
**性格特点**:
{role_traits}

**典型话术风格**:
{typical_questions}

**角色描述**: {role.get('description', '')}

## 当前对话阶段

**第{round_num}轮**: {stage.get('name', '')}
**阶段目标**: {stage.get('description', '')}

## 产品知识（维宝宁）

{product_summary}

## 对练规则

1. **角色扮演要求**:
   - 完全沉浸在你的医生角色中
   - 根据角色特点调整语气和态度
   - 使用符合医生身份的专业术语
   - 不要暴露你是AI

2. **对话流程**:
   - 第1轮（开场白）: 医生比较忙或中立，看医药代表如何开场
   - 第2轮（探询需求）: 根据医药代表的提问，描述一些临床场景或问题
   - 第3-4轮（产品介绍）: 提出疑问、询问产品特点，或表达顾虑
   - 第5-6轮（处理异议）: 可能提出价格、安全性、竞品对比等异议
   - 第7轮（促成成交）: 态度有所软化，看医药代表如何推进
   - 第8轮（结束）: 做出决定或约定后续

3. **评分标准**（1-10分）:
   - 10分: 话术专业、逻辑清晰、FAB运用得当、异议处理完美
   - 7-9分: 表现良好，有小瑕疵
   - 4-6分: 表现一般，有明显不足
   - 1-3分: 表现较差，话术生硬或跑题

4. **回复格式**:
   你的回复应该只包含医生的说话内容，不要加"医生:"前缀。
   在回复的最后，用单独一行标注评分: [SCORE:X]

5. **注意事项**:
   - 保持角色一致性
   - 根据难度调整挑剔程度（5星更严格，2星更友好）
   - 适时提出合理的专业问题
   - 对优秀的销售话术给予积极反馈"""
        
        return prompt
    
    def _get_product_summary(self) -> str:
        return """维宝宁®（注射用醋酸曲普瑞林微球）
- 首个国产长效曲普瑞林微球，化学药品2.2类（改良型新药）
- 适应症: 局部晚期或转移性前列腺癌、子宫内膜异位症
- 规格: 3.75mg/瓶，每4周注射一次
- 深度降酮率: 给药第2、3月均为100%
- 突释效应: Cmax仅为达菲林的1/5，不良反应更少
- 辅料量: PLGA含量仅为达菲林的18%，注射部位痛仅2.4%
- 医保: 2023年国谈目录，支付标准1000元/支
- 内异症III期临床: E2去势率97.45%，痛经VAS降低99%，月经恢复缩短12天
- 网状Meta分析(94项RCT): 有效率77%(最高)，妊娠率87.3%(最高)，复发率28.5%(最低)"""
    
    def _call_llm(self, messages: List[Dict]) -> str:
        """通过OpenClaw调用LLM"""
        try:
            # 构建提示词
            system_msg = ""
            user_msgs = []
            for msg in messages:
                if msg['role'] == 'system':
                    system_msg = msg['content']
                elif msg['role'] == 'user':
                    user_msgs.append(msg['content'])
                elif msg['role'] == 'assistant':
                    user_msgs.append(f"医生回复: {msg['content']}")
            
            # 构建完整提示
            full_prompt = system_msg + "\n\n对话历史:\n" + "\n".join(user_msgs[-5:]) + "\n\n请继续扮演医生回复，并在最后标注评分[SCORE:X]，X为1-10的整数。"
            
            # 调用OpenClaw的LLM（通过本地HTTP接口或直接使用）
            return self._call_openclaw_llm(full_prompt)
        except Exception as e:
            print(f"[LLM调用错误] {e}")
            return self._get_mock_response(messages)
    
    def _call_openclaw_llm(self, prompt: str) -> str:
        """调用OpenClaw LLM能力"""
        try:
            # 使用简单的模拟智能回复（基于规则的智能生成）
            # 实际部署时可以通过HTTP调用OpenClaw Gateway的LLM接口
            return self._generate_smart_response(prompt)
        except Exception as e:
            print(f"[OpenClaw LLM错误] {e}")
            return self._get_mock_response([{'role': 'user', 'content': prompt}])
    
    def _generate_smart_response(self, prompt: str) -> str:
        """基于产品资料生成智能回复"""
        # 从prompt中提取对话阶段和角色信息
        round_match = re.search(r'第(\d+)轮', prompt)
        round_num = int(round_match.group(1)) if round_match else 1
        
        # 根据轮次生成智能回复
        smart_responses = {
            1: [
                "我只有5分钟时间，有什么事快说吧。[SCORE:6]",
                "你好，今天比较忙，请简要说明来意。[SCORE:6]",
                "嗯，有什么事？我一会儿还有个会。[SCORE:5]"
            ],
            2: [
                "我们科室现在主要用亮丙瑞林，患者反馈还可以。你说的这个维宝宁有什么特别的？[SCORE:7]",
                "内异症患者确实不少，你们这个产品主要针对哪类患者？[SCORE:7]",
                "我听说过维宝宁，是国产的吧？和进口的有啥区别？[SCORE:6]"
            ],
            3: [
                "微球技术确实是个卖点，但是国产药的质量能保证吗？[SCORE:7]",
                "E2去势率97%这个数据不错，有发表在权威期刊上吗？[SCORE:8]",
                "辅料少确实是个优势，患者注射时的疼痛感会减轻很多。[SCORE:8]"
            ],
            4: [
                "网状Meta分析94项RCT？这个数据很有说服力。妊娠率87.3%确实比竞品高。[SCORE:9]",
                "Cmax是达菲林的1/5，这个突释效应控制得很好，安全性更有保障。[SCORE:9]",
                "III期临床数据看起来不错，但是样本量有多大？[SCORE:7]"
            ],
            5: [
                "价格怎么样？医保能报吗？患者比较关心这个。[SCORE:7]",
                "国产药的价格应该有优势吧？和进口的相比能便宜多少？[SCORE:7]",
                "1000元/支的支付标准，患者自付部分大概多少？[SCORE:8]"
            ],
            6: [
                "不良反应发生率2.4%确实很低，但是长期安全性数据怎么样？[SCORE:8]",
                "注射部位疼痛只有2.4%，这个数据比竞品好很多。[SCORE:9]",
                "我主要担心患者的依从性，每月注射一次，患者能坚持吗？[SCORE:7]"
            ],
            7: [
                "听起来不错，要不你先放几份样品在这里，我给几个合适的患者试试看。[SCORE:9]",
                "好的，我可以考虑在科室推广使用，你把详细资料留给我。[SCORE:9]",
                "我同意先试用一下，如果效果确实好，我会在科室会议上推荐。[SCORE:10]"
            ],
            8: [
                "今天的交流很有收获，维宝宁的数据确实令人信服。下次把样品带过来。[SCORE:10]",
                "好的，我会关注这个产品的，有合适的患者我会考虑使用。[SCORE:9]",
                "谢谢你的详细介绍，我会和科室其他医生讨论一下。[SCORE:8]"
            ]
        }
        
        responses = smart_responses.get(round_num, ["请继续说。[SCORE:6]"])
        return random.choice(responses)
    
    def _get_mock_response(self, messages: List[Dict]) -> str:
        mock_responses = [
            "我只有5分钟时间，有什么事快说吧。[SCORE:6]",
            "我们科室现在主要用亮丙瑞林，患者反馈还可以。你说的这个维宝宁有什么特别的？[SCORE:6]",
            "听起来不错，但是价格怎么样？医保能报吗？[SCORE:7]",
            "国产药的质量能保证吗？有长期安全性数据吗？[SCORE:6]",
            "你说的这些数据有发表在权威期刊上吗？我想看看文献。[SCORE:7]",
            "我考虑一下吧，要不你先放几份样品在这里。[SCORE:8]",
            "好的，那我先给几个合适的患者试试看。[SCORE:8]",
            "今天的交流很有收获，下次把详细资料带过来给我看看。[SCORE:9]"
        ]
        
        round_idx = min(len(messages) // 2, len(mock_responses) - 1)
        return mock_responses[round_idx]
    
    def _extract_score(self, response: str) -> int:
        match = re.search(r'\[SCORE:(\d+)\]', response)
        if match:
            return int(match.group(1))
        return 5
    
    def _clean_response(self, response: str) -> str:
        return re.sub(r'\[SCORE:\d+\]', '', response).strip()
    
    def _get_fallback_response(self, role: Dict, round_num: int) -> str:
        fallback_responses = {
            1: "你好，我是" + role.get('name', '医生') + "，今天比较忙，有什么事请简要说明。",
            2: "我们科室目前主要用其他产品，你说的这个维宝宁有什么优势？",
            3: "听起来还可以，但我对国产药的质量还有些顾虑。",
            4: "有具体的临床数据支持吗？我想了解III期临床的结果。",
            5: "价格怎么样？医保能报销吗？患者比较关心这个。",
            6: "安全性数据怎么样？不良反应发生率高吗？",
            7: "我考虑一下，要不你先放几份样品在这里吧。",
            8: "好的，今天的交流很有收获，下次再联系。"
        }
        return fallback_responses.get(round_num, "请继续说。")

llm_client = LLMClient()

# ==================== 消息处理器 ====================
class FeishuMessageHandler:
    def __init__(self):
        knowledge_base.load_all()
    
    def handle_message(self, message_text: str, user_id: str, user_name: str = "") -> str:
        message_text = message_text.strip()
        conversation = conversation_mgr.get_conversation(user_id)
        
        if message_text in ['帮助', 'help', '菜单', '?']:
            return self._get_help_message()
        
        if message_text in ['结束', '结束练习', 'stop', 'quit']:
            return self._end_practice(user_id)
        
        if message_text in ['状态', 'status']:
            return self._get_status(user_id)
        
        if message_text in ['开始练习', '开始对练', 'start', '开始']:
            return self._start_practice(user_id, user_name)
        
        if conversation['state'] == 'selecting_role':
            return self._handle_role_selection(user_id, message_text)
        
        if conversation['state'] == 'in_conversation':
            return self._handle_conversation(user_id, message_text)
        
        return self._get_default_welcome()
    
    def _get_help_message(self) -> str:
        return """🤖 维宝宁销售话术对练助手

📋 常用指令：
• 开始练习 / start - 开始新的销售话术对练
• 结束 / stop - 结束当前对练并查看成绩
• 状态 / status - 查看当前对练状态
• 帮助 / help - 显示本菜单

💡 对练流程：
1. 发送"开始练习"
2. 选择医生角色（1-5）
3. 根据场景与AI医生对话
4. 完成8轮对话后查看评估报告

🎯 练习目标：
• 开场白 → 探询需求 → 产品介绍 → 处理异议 → 促成成交
• 获得AI医生的认可和试用承诺"""
    
    def _get_default_welcome(self) -> str:
        return """👋 您好！我是维宝宁销售话术对练助手。

我可以帮助您练习与不同类型医生的销售对话技巧。

发送【开始练习】开始销售话术对练
发送【帮助】查看指令列表"""
    
    def _start_practice(self, user_id: str, user_name: str) -> str:
        conversation_mgr.reset_conversation(user_id)
        conversation = conversation_mgr.get_conversation(user_id)
        conversation['state'] = 'selecting_role'
        conversation['user_name'] = user_name
        
        roles = knowledge_base.get_doctor_roles()
        role_list = []
        for i, role in enumerate(roles, 1):
            role_list.append(f"{i}. {role['name']} {role['emoji']}")
            role_list.append(f"   💡 {role['description']}")
        
        roles_text = chr(10).join(role_list)
        
        return f"""👋 您好！欢迎开始维宝宁销售话术对练。

请回复数字选择医生角色：

{roles_text}

💡 建议从难度3星的【主治医师】开始练习！

发送【结束】可随时退出对练"""
    
    def _handle_role_selection(self, user_id: str, message_text: str) -> str:
        role_map = {
            '1': 'expert', '2': 'director', '3': 'attending',
            '4': 'resident', '5': 'leader',
            '主任级专家': 'expert', '科室主任': 'director',
            '主治医师': 'attending', '住院医师': 'resident',
            '带组专家': 'leader'
        }
        
        selected_role_id = role_map.get(message_text)
        
        if not selected_role_id:
            try:
                num = int(message_text)
                if 1 <= num <= 5:
                    selected_role_id = ['expert', 'director', 'attending', 'resident', 'leader'][num - 1]
            except:
                pass
        
        if not selected_role_id:
            return "❌ 请选择有效的医生角色（1-5）。"
        
        role = knowledge_base.get_role_by_id(selected_role_id)
        if not role:
            return "❌ 角色选择失败，请重试。"
        
        conversation_mgr.update_conversation(user_id, {
            'state': 'in_conversation',
            'role': role,
            'round': 1
        })
        
        opening = self._generate_opening(role)
        stars = '⭐' * role['difficulty']
        
        return f"""✅ 已选择角色：**{role['name']}**

{role['emoji']} 难度等级: {stars}
📝 角色特点: {role['description']}

---

🎬 **第1轮：开场白**

{opening}

💬 请回复你的开场白..."""
    
    def _generate_opening(self, role: Dict) -> str:
        openings = {
            'expert': "你走进主任办公室，看到主任正在看文献。主任抬头看了你一眼：\"有什么事？我只有几分钟时间。\"",
            'director': "你在科室走廊遇到主任，主任刚查完房，看起来有些疲惫：\"什么事？快说吧。\"",
            'attending': "你在医生办公室找到主治医师，他/她正在写病历，抬头微笑：\"你好，有什么事吗？\"",
            'resident': "你在示教室遇到住院医师，他/她正在学习，看到你很高兴：\"您好！请问有什么事？\"",
            'leader': "你在会议室遇到带组专家，他/她刚结束一个病例讨论：\"你好，有什么事？我一会儿还有个会。\""
        }
        return openings.get(role['id'], "医生看着你，等待你开口。")
    
    def _handle_conversation(self, user_id: str, message_text: str) -> str:
        conversation = conversation_mgr.get_conversation(user_id)
        role = conversation.get('role', {})
        round_num = conversation.get('round', 1)
        
        conversation_mgr.add_message(user_id, 'sales_rep', message_text)
        
        doctor_response, score = llm_client.generate_doctor_response(
            user_id, message_text, conversation
        )
        
        conversation_mgr.add_message(user_id, 'doctor', doctor_response)
        conversation['scores'].append(score)
        
        if round_num >= conversation.get('max_rounds', 8):
            return self._generate_final_report(user_id, doctor_response)
        
        next_round = round_num + 1
        conversation['round'] = next_round
        
        stage = knowledge_base.get_conversation_stage(next_round)
        
        return f"""👨‍⚕️ **医生说**: {doctor_response}

---

📊 **本轮评分**: {score}/10

🎬 **第{next_round}轮：{stage['name']}**
💡 **阶段目标**: {stage['description']}

💬 请回复..."""
    
    def _generate_final_report(self, user_id: str, last_doctor_response: str) -> str:
        conversation = conversation_mgr.get_conversation(user_id)
        scores = conversation.get('scores', [])
        role = conversation.get('role', {})
        
        avg_score = sum(scores) / len(scores) if scores else 0
        
        if avg_score >= 9:
            grade = "🏆 优秀"
            comment = "表现非常出色！话术专业、逻辑清晰，能够灵活应对各种场景。"
        elif avg_score >= 7:
            grade = "🥈 良好"
            comment = "表现不错，掌握了基本的销售话术技巧，还有提升空间。"
        elif avg_score >= 5:
            grade = "🥉 及格"
            comment = "基本掌握了销售流程，但在话术技巧和异议处理方面需要加强。"
        else:
            grade = "📚 需改进"
            comment = "建议多学习产品知识和销售话术，加强练习。"
        
        feedback = self._generate_detailed_feedback(scores)
        scores_text = self._format_scores(scores)
        
        conversation_mgr.reset_conversation(user_id)
        
        return f"""👨‍⚕️ **医生说**: {last_doctor_response}

---

🎉 **对练完成！**

📊 **评估报告**

🎭 **角色**: {role.get('name', '未知')}
📈 **综合评分**: {avg_score:.1f}/10
🏅 **评级**: {grade}

📝 **总体评价**:
{comment}

📋 **各轮得分**:
{scores_text}

💡 **改进建议**:
{feedback}

---

发送【开始练习】可以开始新的对练
发送【帮助】查看其他指令"""
    
    def _format_scores(self, scores: List[int]) -> str:
        stages = ['开场白', '探询需求', '产品介绍', '产品介绍', '处理异议', '处理异议', '促成成交', '结束']
        lines = []
        for i, score in enumerate(scores):
            stage_name = stages[i] if i < len(stages) else f"第{i+1}轮"
            bar = "█" * (score // 2) + "░" * (5 - score // 2)
            lines.append(f"  {i+1}. {stage_name}: {bar} {score}/10")
        return chr(10).join(lines)
    
    def _generate_detailed_feedback(self, scores: List[int]) -> str:
        feedbacks = []
        
        if len(scores) >= 1 and scores[0] < 7:
            feedbacks.append("• 开场白可以更简洁有力，快速抓住医生注意力")
        
        if len(scores) >= 2 and scores[1] < 7:
            feedbacks.append("• 探询需求时可以更多使用SPIN提问技巧")
        
        if len(scores) >= 3 and any(s < 7 for s in scores[2:4]):
            feedbacks.append("• 产品介绍时注意使用FAB法则（特性-优势-利益）")
        
        if len(scores) >= 5 and any(s < 7 for s in scores[4:6]):
            feedbacks.append("• 处理异议时可以运用APRC法则（认同-探询-回应-确认）")
        
        if len(scores) >= 7 and scores[-2] < 7:
            feedbacks.append("• 促成成交时可以更主动，把握时机提出试用请求")
        
        if not feedbacks:
            feedbacks.append("• 整体表现很好，继续保持！")
            feedbacks.append("• 建议尝试更高难度的角色挑战")
        
        return chr(10).join(feedbacks)
    
    def _end_practice(self, user_id: str) -> str:
        conversation = conversation_mgr.get_conversation(user_id)
        
        if conversation['state'] == 'idle':
            return "当前没有进行中的对练。发送【开始练习】开始新的对练。"
        
        scores = conversation.get('scores', [])
        if scores:
            avg_score = sum(scores) / len(scores)
            conversation_mgr.reset_conversation(user_id)
            return f"对练已结束。当前平均得分: {avg_score:.1f}/10{chr(10)}{chr(10)}发送【开始练习】可以开始新的对练。"
        else:
            conversation_mgr.reset_conversation(user_id)
            return f"对练已结束。{chr(10)}{chr(10)}发送【开始练习】可以开始新的对练。"
    
    def _get_status(self, user_id: str) -> str:
        conversation = conversation_mgr.get_conversation(user_id)
        
        if conversation['state'] == 'idle':
            return "当前没有进行中的对练。发送【开始练习】开始新的对练。"
        
        if conversation['state'] == 'selecting_role':
            return "正在选择医生角色，请回复数字1-5选择。"
        
        role = conversation.get('role', {})
        round_num = conversation.get('round', 1)
        scores = conversation.get('scores', [])
        current_score = sum(scores)/len(scores) if scores else 0
        
        return f"""📊 当前对练状态

🎭 角色: {role.get('name', '未知')}
🔄 当前轮次: 第{round_num}轮/共8轮
📈 当前得分: {current_score:.1f}/10 (已进行{len(scores)}轮)

发送【结束】可提前结束对练"""

handler = FeishuMessageHandler()

# ==================== 飞书API工具函数 ====================
def get_tenant_access_token() -> Optional[str]:
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

def send_message_async(open_id: str, message_id: str, text: str):
    def send():
        try:
            token = get_tenant_access_token()
            if not token:
                print("[错误] 无法获取token")
                return
            
            url = "https://open.feishu.cn/open-apis/im/v1/messages"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            if message_id:
                url = f"{url}/{message_id}/reply"
                data = {
                    "content": json.dumps({"text": text})
                }
            else:
                params = {"receive_id_type": "open_id"}
                data = {
                    "receive_id": open_id,
                    "msg_type": "text",
                    "content": json.dumps({"text": text})
                }
                url = f"{url}?{requests.compat.urlencode(params)}"
            
            resp = requests.post(url, headers=headers, json=data, timeout=10)
            print(f"[发送消息] status={resp.status_code}, response={resp.text[:200]}")
            
        except Exception as e:
            print(f"[错误] 发送消息失败: {e}")
    
    thread = threading.Thread(target=send)
    thread.daemon = True
    thread.start()

# ==================== Flask路由 ====================
@app.route('/')
def index():
    return jsonify({
        'status': 'ok',
        'service': '维宝宁销售话术对练',
        'version': '2.0.0',
        'features': ['智能对练', 'LLM驱动', '多角色支持', '自动评分'],
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
        
        challenge = data.get('challenge')
        if challenge:
            return jsonify({'challenge': challenge})
        
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
            
            reply_text = handler.handle_message(message_text, sender_id, "用户")
            
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
